#!/usr/bin/env python3
"""Turn a stock better-sqlite3-multiple-ciphers 12.x source tree into what Granola needs.

Granola ships a patched fork with a native Database#updateHook() but no longer
bundles its C++ source, so we rebuild upstream with three changes:

1. V8 15 (Electron 45+): GetPrototypeV2()/HolderV2() are gone again; use
   GetPrototype()/Holder().
2. updateHook(fn): wraps sqlite3_update_hook. fn(op, dbName, table, rowid), with op
   being "insert", "update" or "delete". Exceptions thrown by fn are swallowed.
3. SQLITE_ENABLE_BYTECODE_VTAB: Granola's live queries read the tables_used()
   virtual table. This is the only compile option that differs from the macOS binary.

Usage: patch-bs3.py <package-dir>   (idempotent; fails loudly if upstream changed)
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])


def patch(rel, pairs):
    p = root / rel
    s = p.read_text()
    for old, new, marker in pairs:
        if marker in s:
            continue
        if s.count(old) != 1:
            sys.exit(f"patch-bs3: anchor not found exactly once in {rel}: {old[:60]!r}")
        s = s.replace(old, new)
    p.write_text(s)


patch("src/util/macros.cpp", [
    (
        "#if defined(V8_MAJOR_VERSION) && V8_MAJOR_VERSION >= 13\n// v8::Object::GetPrototype",
        "#if defined(V8_MAJOR_VERSION) && V8_MAJOR_VERSION >= 13 && V8_MAJOR_VERSION < 15\n// v8::Object::GetPrototype",
        "V8_MAJOR_VERSION >= 13 && V8_MAJOR_VERSION < 15",
    ),
    (
        "#if defined(V8_MAJOR_VERSION) && V8_MAJOR_VERSION >= 13\n#define PROPERTY_HOLDER(info) (info).HolderV2()",
        "#if defined(V8_MAJOR_VERSION) && V8_MAJOR_VERSION >= 15\n#define PROPERTY_HOLDER(info) (info).Holder()\n"
        "#elif defined(V8_MAJOR_VERSION) && V8_MAJOR_VERSION >= 13\n#define PROPERTY_HOLDER(info) (info).HolderV2()",
        "#define PROPERTY_HOLDER(info) (info).Holder()",
    ),
])

patch("src/objects/database.hpp", [
    (
        "\tstatic NODE_METHOD(JS_unsafeMode);\n",
        "\tstatic NODE_METHOD(JS_unsafeMode);\n\tstatic NODE_METHOD(JS_updateHook);\n"
        "\tstatic void UpdateHookCallback(void* self, int op, const char* db_name, const char* table, sqlite3_int64 rowid);\n",
        "JS_updateHook",
    ),
    (
        "\tconst v8::Global<v8::Value> logger;\n",
        "\tconst v8::Global<v8::Value> logger;\n\tv8::Global<v8::Function> update_hook;\n\tv8::Isolate* const hook_isolate;\n",
        "hook_isolate",
    ),
])

HOOK_IMPL = '''NODE_METHOD(Database::JS_updateHook) {
	Database* db = Unwrap<Database>(info.This());
	REQUIRE_DATABASE_OPEN(db->GetState());
	if (info.Length() == 0 || info[0]->IsNull() || info[0]->IsUndefined()) {
		sqlite3_update_hook(db->db_handle, NULL, NULL);
		db->update_hook.Reset();
		return;
	}
	REQUIRE_ARGUMENT_FUNCTION(first, v8::Local<v8::Function> fn);
	db->update_hook.Reset(OnlyIsolate, fn);
	sqlite3_update_hook(db->db_handle, UpdateHookCallback, db);
}

void Database::UpdateHookCallback(void* self, int op, const char* db_name, const char* table, sqlite3_int64 rowid) {
	Database* db = static_cast<Database*>(self);
	if (db->update_hook.IsEmpty()) return;
	v8::Isolate* isolate = db->hook_isolate;
	v8::HandleScope scope(isolate);
	v8::Local<v8::Context> ctx = isolate->GetCurrentContext();
	const char* op_name = op == SQLITE_INSERT ? "insert" : op == SQLITE_UPDATE ? "update" : op == SQLITE_DELETE ? "delete" : "unknown";
	v8::Local<v8::Value> args[4] = {
		StringFromUtf8(isolate, op_name, -1),
		StringFromUtf8(isolate, db_name, -1),
		StringFromUtf8(isolate, table, -1),
		db->safe_ints ? v8::Local<v8::Value>(v8::BigInt::New(isolate, rowid)) : v8::Local<v8::Value>(v8::Number::New(isolate, static_cast<double>(rowid))),
	};
	v8::TryCatch try_catch(isolate);
	(void)db->update_hook.Get(isolate)->Call(ctx, v8::Undefined(isolate), 4, args);
}

NODE_GETTER(Database::JS_open) {'''

patch("src/objects/database.cpp", [
    (
        '\tSetPrototypeMethod(isolate, data, t, "unsafeMode", JS_unsafeMode);\n',
        '\tSetPrototypeMethod(isolate, data, t, "unsafeMode", JS_unsafeMode);\n'
        '\tSetPrototypeMethod(isolate, data, t, "updateHook", JS_updateHook);\n',
        '"updateHook", JS_updateHook',
    ),
    (
        "\tlogger(isolate, logger),\n",
        "\tlogger(isolate, logger),\n\thook_isolate(isolate),\n",
        "hook_isolate(isolate)",
    ),
    (
        "\t\tbackups.clear();\n\t\tint status = sqlite3_close(db_handle);",
        "\t\tbackups.clear();\n\t\tsqlite3_update_hook(db_handle, NULL, NULL);\n\t\tupdate_hook.Reset();\n\t\tint status = sqlite3_close(db_handle);",
        "sqlite3_update_hook(db_handle, NULL, NULL);",
    ),
    ("NODE_GETTER(Database::JS_open) {", HOOK_IMPL, "UpdateHookCallback(void* self"),
])

patch("deps/defines.gypi", [
    (
        "'SQLITE_ENABLE_STAT4',",
        "'SQLITE_ENABLE_STAT4',\n      'SQLITE_ENABLE_BYTECODE_VTAB',",
        "SQLITE_ENABLE_BYTECODE_VTAB",
    ),
])

print("    patched better-sqlite3 source (V8 15, updateHook, BYTECODE_VTAB)")
