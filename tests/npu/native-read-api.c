#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <limits.h>
#include <stdint.h>
#include <unicorn/unicorn.h>
#include <unicorn/riscv.h>

_Static_assert(sizeof(void *) == 8 && sizeof(size_t) == 8, "reviewed 64-bit host API required");

enum FieldName {
    F_UCH, F_VALUE, F_DICT, F_CPU, F_CODE, F_EXECUTIONS, F_SAMPLER, F_WORD_READER,
    F_RECORD, F_EVENTS, F_CSR_EVENTS, F_DONE_TRACKING, F_PACKET_TRACKING, F_RX_TRACKING,
    F_TRACKING, F_PROBING, F_RPC_ACTIVE, F_DENY_TYPE, F_INTERCEPT, F_STOPS, F_SKIP_ONCE,
    F_PENDING_CALL, F_RETURN_PC, F_LAST_CSR, F_TICK, F_STUB_COUNTS, F_HART, F_HART_CSR,
    F_HOOK_EXCEPTION, F_BLOCK_CACHE, F_COUNTS, F_MIN_SP, F_BLOCKS, F_COUNT
};
static const char *const field_names[F_COUNT] = {
    "_uch", "value", "__dict__", "cpu", "code", "executions", "csr_sampler", "get32",
    "record", "events", "csr_events", "done_tracking", "packet_tracking", "rx_tracking",
    "tracking", "probing", "rpc_active", "deny_type", "intercept", "stops", "skip_once",
    "pending_call", "return_pc", "last_csr", "tick", "stub_counts", "hart", "mhartid-csr",
    "_hook_exception", "block_cache", "counts", "min_sp", "blocks"
};
static PyObject *field_keys[F_COUNT];

static PyObject *dict_field(PyObject *dictionary, enum FieldName field)
{
    return PyDict_GetItemWithError(dictionary, field_keys[field]);
}

typedef uc_err (*read_register_fn)(uc_engine *, int, void *);
typedef uc_err (*read_batch_fn)(uc_engine *, const int *, void **, int);
typedef uc_err (*read_memory_fn)(uc_engine *, uint64_t, void *, uint64_t);
typedef uc_err (*emulate_fn)(uc_engine *, uint64_t, uint64_t, uint64_t, size_t);

typedef struct {
    PyObject_HEAD
    PyObject *cpu;
    PyObject *original;
    PyObject *error_type;
    uc_engine *handle;
    unsigned long thread;
    read_register_fn read;
    read_batch_fn batch;
    read_memory_fn memory;
    emulate_fn emulate;
    int registers[3];
} Reader;

static PyTypeObject ReaderType;

typedef struct {
    PyObject_HEAD
    PyObject *owner;
    PyObject *original;
    PyObject *reader;
    PyObject *interesting;
    PyObject *state;
    PyObject *code;
    PyObject *executions;
    PyObject *sampler;
    PyObject *word_reader;
    uint64_t fast_calls;
    uint64_t reference_calls;
} ColdObserver;

typedef struct {
    PyObject_HEAD
    PyObject *owner;
    PyObject *original;
    PyObject *reader;
    PyObject *state;
    PyObject *counter_type;
    uint64_t fast_calls;
    uint64_t reference_calls;
    uint64_t inactive_calls;
} BlockObserver;

static void *engine_handle(PyObject *cpu)
{
    PyObject *handle = PyObject_GetAttr(cpu, field_keys[F_UCH]);
    PyObject *value;
    void *result;

    if (!handle)
        return NULL;
    value = PyObject_GetAttr(handle, field_keys[F_VALUE]);
    Py_DECREF(handle);
    if (!value)
        return NULL;
    if (value == Py_None) {
        Py_DECREF(value);
        PyErr_SetString(PyExc_RuntimeError, "native reader engine handle is null");
        return NULL;
    }
    result = PyLong_AsVoidPtr(value);
    Py_DECREF(value);
    if (!result && !PyErr_Occurred())
        PyErr_SetString(PyExc_RuntimeError, "native reader engine handle is null");
    return result;
}

static int check_reader(Reader *self)
{
    void *current;

    if (!self->cpu || !self->original || !self->error_type) {
        PyErr_SetString(PyExc_RuntimeError, "native reader is not initialized");
        return 0;
    }
    if (PyThread_get_thread_ident() != self->thread) {
        PyErr_SetString(PyExc_RuntimeError, "native reader is per-engine and per-thread");
        return 0;
    }
    current = engine_handle(self->cpu);
    if (!current)
        return 0;
    if (current != self->handle) {
        PyErr_SetString(PyExc_RuntimeError, "native reader engine handle changed");
        return 0;
    }
    return 1;
}

static PyObject *backend_error(Reader *self, int status, int register_id, int scalar)
{
    PyObject *error = scalar ? PyObject_CallFunction(self->error_type, "ii", status, register_id) :
                             PyObject_CallFunction(self->error_type, "i", status);
    if (error) {
        PyErr_SetObject(self->error_type, error);
        Py_DECREF(error);
    }
    return NULL;
}

static PyObject *reader_call(PyObject *object, PyObject *args, PyObject *kwargs)
{
    Reader *self = (Reader *)object;
    PyObject *argument;
    uint64_t value = 0;
    long register_id;
    int overflow, status;

    if (!check_reader(self))
        return NULL;
    if ((kwargs && PyDict_Size(kwargs)) || PyTuple_GET_SIZE(args) != 1)
        return PyObject_Call(self->original, args, kwargs);
    argument = PyTuple_GET_ITEM(args, 0);
    if (!PyLong_CheckExact(argument))
        return PyObject_Call(self->original, args, kwargs);
    register_id = PyLong_AsLongAndOverflow(argument, &overflow);
    if (PyErr_Occurred())
        return NULL;
    if (overflow || register_id < INT_MIN || register_id > INT_MAX)
        return PyObject_Call(self->original, args, kwargs);
    status = self->read(self->handle, (int)register_id, &value);
    if (status)
        return backend_error(self, status, (int)register_id, 1);
    return PyLong_FromUnsignedLongLong(value);
}

static PyObject *reader_csrs(Reader *self, PyObject *unused)
{
    uint64_t values[3] = {0, 0, 0};
    void *pointers[3] = {&values[0], &values[1], &values[2]};
    int status;

    (void)unused;
    if (!check_reader(self))
        return NULL;
    status = self->batch(self->handle, self->registers, pointers, 3);
    if (status)
        return backend_error(self, status, 0, 0);
    return Py_BuildValue("(KKK)", (unsigned long long)values[0],
                         (unsigned long long)values[1], (unsigned long long)values[2]);
}

static PyObject *reader_u32(Reader *self, PyObject *argument)
{
    unsigned long long address;
    unsigned char bytes[4] = {0, 0, 0, 0};
    uint32_t value;
    int status;

    if (!check_reader(self))
        return NULL;
    if (!self->memory) {
        PyErr_SetString(PyExc_RuntimeError, "native reader has no reviewed memory API");
        return NULL;
    }
    if (!PyLong_CheckExact(argument)) {
        PyErr_SetString(PyExc_TypeError, "memory word address must be an exact integer");
        return NULL;
    }
    address = PyLong_AsUnsignedLongLong(argument);
    if (PyErr_Occurred())
        return NULL;
    if (address > UINT64_MAX - 3) {
        PyErr_SetString(PyExc_OverflowError, "memory word spans the u64 address range");
        return NULL;
    }
    status = self->memory(self->handle, (uint64_t)address, bytes, sizeof(bytes));
    if (status)
        return backend_error(self, status, 0, 0);
    value = (uint32_t)bytes[0] | (uint32_t)bytes[1] << 8 |
            (uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24;
    return PyLong_FromUnsignedLong(value);
}

static PyObject *reader_bind_emulator(Reader *self, PyObject *argument)
{
    unsigned long long address;

    if (!check_reader(self))
        return NULL;
    if (self->emulate) {
        PyErr_SetString(PyExc_RuntimeError, "native emulator is already bound");
        return NULL;
    }
    if (!PyLong_CheckExact(argument)) {
        PyErr_SetString(PyExc_TypeError, "native emulator API address must be an exact integer");
        return NULL;
    }
    address = PyLong_AsUnsignedLongLong(argument);
    if (PyErr_Occurred())
        return NULL;
    if (!address) {
        PyErr_SetString(PyExc_ValueError, "native emulator API address is invalid");
        return NULL;
    }
    self->emulate = (emulate_fn)(uintptr_t)address;
    Py_RETURN_NONE;
}

static PyObject *reader_emulate(Reader *self, PyObject *args, PyObject *kwargs)
{
    PyObject *arguments[4] = {NULL, NULL, NULL, NULL}, *error;
    unsigned long long values[4] = {0, 0, 0, 0};
    int status;
    static char *names[] = {"begin", "until", "timeout", "count", NULL};

    if (!check_reader(self))
        return NULL;
    if (!self->emulate) {
        PyErr_SetString(PyExc_RuntimeError, "native emulator has no reviewed API");
        return NULL;
    }
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|OO:emulate", names,
        &arguments[0], &arguments[1], &arguments[2], &arguments[3]))
        return NULL;
    for (int i = 0; i < 4; i++) {
        if (!arguments[i])
            continue;
        if (!PyLong_CheckExact(arguments[i])) {
            PyErr_SetString(PyExc_TypeError, "native emulator bounds must be exact unsigned integers");
            return NULL;
        }
        values[i] = PyLong_AsUnsignedLongLong(arguments[i]);
        if (PyErr_Occurred())
            return NULL;
    }
    if (PyObject_SetAttr(self->cpu, field_keys[F_HOOK_EXCEPTION], Py_None) < 0)
        return NULL;
    /* Keep the calling GIL attached across the same native API and timeout. */
    status = self->emulate(self->handle, (uint64_t)values[0], (uint64_t)values[1],
        (uint64_t)values[2], (size_t)values[3]);
    if (PyErr_Occurred() || PyErr_CheckSignals() < 0)
        return NULL;
    if (status)
        return backend_error(self, status, 0, 0);
    error = PyObject_GetAttr(self->cpu, field_keys[F_HOOK_EXCEPTION]);
    if (!error)
        return NULL;
    if (error != Py_None) {
        if (PyExceptionInstance_Check(error))
            PyErr_SetObject((PyObject *)Py_TYPE(error), error);
        else
            PyErr_SetString(PyExc_TypeError, "exceptions must derive from BaseException");
        Py_DECREF(error);
        return NULL;
    }
    Py_DECREF(error);
    Py_RETURN_NONE;
}

static int increment_item(PyObject *dictionary, PyObject *key)
{
    PyObject *old = PyDict_GetItemWithError(dictionary, key);
    PyObject *one, *next;
    int result;

    if (!old && PyErr_Occurred())
        return 0;
    if (!old) {
        next = PyLong_FromLong(1);
    } else {
        one = PyLong_FromLong(1);
        if (!one)
            return 0;
        next = PyNumber_Add(old, one);
        Py_DECREF(one);
    }
    if (!next)
        return 0;
    result = PyDict_SetItem(dictionary, key, next);
    Py_DECREF(next);
    return result == 0;
}

static PyObject *cold_reference(ColdObserver *self, PyObject *args, PyObject *kwargs)
{
    self->reference_calls++;
    return PyObject_Call(self->original, args, kwargs);
}

static int cold_csr_record(ColdObserver *self, Reader *reader)
{
    uint64_t values[3] = {0, 0, 0};
    void *pointers[3] = {&values[0], &values[1], &values[2]};
    PyObject *previous = dict_field(self->state, F_LAST_CSR);
    PyObject *fresh = NULL, *args = NULL, *kwargs = NULL, *record = NULL;
    PyObject *method = NULL, *hexes[3] = {NULL, NULL, NULL};
    int equal = 1, status;

    status = reader->batch(reader->handle, reader->registers, pointers, 3);
    if (status) {
        backend_error(reader, status, 0, 0);
        return 0;
    }
    if (!previous || !PyTuple_CheckExact(previous) || PyTuple_GET_SIZE(previous) != 3) {
        equal = 0;
    } else {
        for (int i = 0; i < 3; i++) {
            PyObject *part = PyTuple_GET_ITEM(previous, i);
            if (!PyLong_CheckExact(part) || PyLong_AsUnsignedLongLong(part) != values[i])
                equal = 0;
            if (PyErr_Occurred()) {
                if (!PyErr_ExceptionMatches(PyExc_OverflowError))
                    return 0;
                PyErr_Clear();
                equal = 0;
            }
        }
    }
    if (equal)
        return 1;
    fresh = Py_BuildValue("(KKK)", (unsigned long long)values[0],
        (unsigned long long)values[1], (unsigned long long)values[2]);
    if (!fresh)
        goto failed;
    for (int i = 0; i < 3; i++) {
        hexes[i] = PyNumber_ToBase(PyTuple_GET_ITEM(fresh, i), 16);
        if (!hexes[i])
            goto failed;
    }
    args = Py_BuildValue("(s)", "csr-state");
    kwargs = Py_BuildValue("{s:O,s:O,s:O}", "mstatus", hexes[0], "mie", hexes[1], "mtvec", hexes[2]);
    method = PyObject_GetAttr(self->owner, field_keys[F_RECORD]);
    if (!args || !kwargs || !method)
        goto failed;
    record = PyObject_Call(method, args, kwargs);
    if (!record || PyList_Append(dict_field(self->state, F_CSR_EVENTS), record) < 0 ||
        PyDict_SetItem(self->state, field_keys[F_LAST_CSR], fresh) < 0)
        goto failed;
    status = 1;
    goto done;
failed:
    status = 0;
done:
    for (int i = 0; i < 3; i++)
        Py_XDECREF(hexes[i]);
    Py_XDECREF(fresh);
    Py_XDECREF(args);
    Py_XDECREF(kwargs);
    Py_XDECREF(method);
    Py_XDECREF(record);
    return status;
}

static PyObject *cold_call(PyObject *object, PyObject *args, PyObject *kwargs)
{
    ColdObserver *self = (ColdObserver *)object;
    Reader *reader;
    PyObject *dictionary, *pc_object, *tick, *count, *pending, *value, *events, *csr_events;
    unsigned long long pc;
    unsigned long size;
    int selected;
    static const enum FieldName flags[] = {F_DONE_TRACKING, F_PACKET_TRACKING, F_RX_TRACKING,
        F_TRACKING, F_PROBING, F_RPC_ACTIVE, F_COUNT};

    if (!self->owner || !self->original) {
        PyErr_SetString(PyExc_RuntimeError, "cold observer is not initialized");
        return NULL;
    }
    if (!self->reader || (kwargs && PyDict_Size(kwargs)) || PyTuple_GET_SIZE(args) != 4)
        return cold_reference(self, args, kwargs);
    reader = (Reader *)self->reader;
    if (PyTuple_GET_ITEM(args, 0) != reader->cpu) {
        PyErr_SetString(PyExc_RuntimeError, "cold observer received a different engine");
        return NULL;
    }
    if (!check_reader(reader))
        return NULL;
    dictionary = PyObject_GetAttr(self->owner, field_keys[F_DICT]);
    if (!dictionary)
        return NULL;
    selected = dictionary == self->state;
    Py_DECREF(dictionary);
    events = dict_field(self->state, F_EVENTS);
    csr_events = dict_field(self->state, F_CSR_EVENTS);
    if (!selected || dict_field(self->state, F_CPU) != reader->cpu ||
        dict_field(self->state, F_CODE) != self->code ||
        dict_field(self->state, F_EXECUTIONS) != self->executions ||
        dict_field(self->state, F_SAMPLER) != self->sampler ||
        dict_field(self->state, F_WORD_READER) != self->word_reader ||
        dict_field(self->state, F_RECORD) ||
        !events || !PyList_CheckExact(events) || !csr_events || !PyList_CheckExact(csr_events))
        return cold_reference(self, args, kwargs);
    for (int i = 0; flags[i] != F_COUNT; i++)
        if (dict_field(self->state, flags[i]) != Py_False)
            return cold_reference(self, args, kwargs);
    if (dict_field(self->state, F_DENY_TYPE) != Py_None ||
        dict_field(self->state, F_INTERCEPT) != Py_None)
        return cold_reference(self, args, kwargs);
    pc_object = PyTuple_GET_ITEM(args, 1);
    if (!PyLong_CheckExact(pc_object) || !PyLong_CheckExact(PyTuple_GET_ITEM(args, 2)))
        return cold_reference(self, args, kwargs);
    pc = PyLong_AsUnsignedLongLong(pc_object);
    size = PyLong_AsUnsignedLong(PyTuple_GET_ITEM(args, 2));
    if (PyErr_Occurred())
        return NULL;
    selected = PySet_Contains(self->interesting, pc_object);
    if (selected < 0)
        return NULL;
    value = dict_field(self->state, F_STOPS);
    if (!value || !PySet_CheckExact(value))
        return cold_reference(self, args, kwargs);
    if (!selected)
        selected = PySet_Contains(value, pc_object);
    if (selected < 0)
        return NULL;
    value = dict_field(self->state, F_SKIP_ONCE);
    if (!value || (value != Py_None && !PyLong_CheckExact(value)))
        return cold_reference(self, args, kwargs);
    if (!selected)
        selected = PyObject_RichCompareBool(value, pc_object, Py_EQ);
    if (selected < 0)
        return NULL;
    pending = dict_field(self->state, F_PENDING_CALL);
    if (pending && pending != Py_None) {
        if (!PyDict_CheckExact(pending) || !(value = dict_field(pending, F_RETURN_PC)))
            return cold_reference(self, args, kwargs);
        if (!selected)
            selected = PyObject_RichCompareBool(value, pc_object, Py_EQ);
        if (selected < 0)
            return NULL;
    }
    if (selected || !pending)
        return cold_reference(self, args, kwargs);
    value = dict_field(self->state, F_LAST_CSR);
    if (!value)
        return cold_reference(self, args, kwargs);
    if (value != Py_None) {
        if (!PyTuple_CheckExact(value) || PyTuple_GET_SIZE(value) != 3)
            return cold_reference(self, args, kwargs);
        for (int i = 0; i < 3; i++)
            if (!PyLong_CheckExact(PyTuple_GET_ITEM(value, i)))
                return cold_reference(self, args, kwargs);
    }
    tick = dict_field(self->state, F_TICK);
    count = PyDict_GetItemWithError(self->executions, pc_object);
    if (PyErr_Occurred())
        return NULL;
    if (!tick || !PyLong_CheckExact(tick) || (count && !PyLong_CheckExact(count)))
        return cold_reference(self, args, kwargs);

    /* Preserve per-instruction counts and fresh CSR/code reads at the common PCs. */
    self->fast_calls++;
    if (!increment_item(self->executions, pc_object))
        return NULL;
    selected = increment_item(self->state, field_keys[F_TICK]);
    if (!selected || !cold_csr_record(self, reader))
        return NULL;
    if (size == 4 && pc >= 0x84000000ULL && pc - 0x84000000ULL < (uint64_t)PyBytes_GET_SIZE(self->code)) {
        unsigned char bytes[4] = {0, 0, 0, 0};
        uint32_t word;
        int status;

        if (!check_reader(reader))
            return NULL;
        status = reader->memory(reader->handle, (uint64_t)pc, bytes, sizeof(bytes));
        if (status)
            return backend_error(reader, status, 0, 0);
        word = (uint32_t)bytes[0] | (uint32_t)bytes[1] << 8 |
            (uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24;
        if (word >> 20 == 0xf14 && (word & 0x707f) == 0x2073) {
            PyObject *hart = PyObject_GetAttr(self->owner, field_keys[F_HART]);
            PyObject *result;
            if (!hart)
                return NULL;
            result = PyObject_CallMethod(reader->cpu, "reg_write", "iO", UC_RISCV_REG_X0 + ((word >> 7) & 31), hart);
            Py_DECREF(hart);
            if (!result)
                return NULL;
            Py_DECREF(result);
            result = PyObject_CallMethod(reader->cpu, "reg_write", "iK", UC_RISCV_REG_PC, pc + 4);
            if (!result)
                return NULL;
            Py_DECREF(result);
            value = dict_field(self->state, F_STUB_COUNTS);
            if (!value || !PyDict_CheckExact(value)) {
                PyErr_SetString(PyExc_RuntimeError, "cold observer stub counter changed");
                return NULL;
            }
            selected = increment_item(value, field_keys[F_HART_CSR]);
            if (!selected)
                return NULL;
        }
    }
    Py_RETURN_NONE;
}

static int cold_init(ColdObserver *self, PyObject *args, PyObject *kwargs)
{
    PyObject *owner, *original;
    static char *names[] = {"owner", "original", NULL};

    if (self->owner) {
        PyErr_SetString(PyExc_RuntimeError, "cold observer cannot be rebound");
        return -1;
    }
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", names, &owner, &original))
        return -1;
    if (!PyCallable_Check(original)) {
        PyErr_SetString(PyExc_TypeError, "cold observer requires the reference instruction callback");
        return -1;
    }
    self->owner = Py_NewRef(owner);
    self->original = Py_NewRef(original);
    return 0;
}

static PyObject *cold_enable(ColdObserver *self, PyObject *args)
{
    Reader *reader;
    PyObject *interesting, *state, *code, *executions, *sampler, *word_reader;

    if (!self->owner || self->reader) {
        PyErr_SetString(PyExc_RuntimeError, "cold observer is uninitialized or already enabled");
        return NULL;
    }
    if (!PyArg_ParseTuple(args, "O!O!", &ReaderType, &reader, &PyFrozenSet_Type, &interesting))
        return NULL;
    if (!check_reader(reader))
        return NULL;
    if (!reader->memory || reader->registers[0] != UC_RISCV_REG_MSTATUS ||
        reader->registers[1] != UC_RISCV_REG_MIE || reader->registers[2] != UC_RISCV_REG_MTVEC) {
        PyErr_SetString(PyExc_RuntimeError, "cold observer requires the reviewed memory and CSR API");
        return NULL;
    }
    state = PyObject_GetAttr(self->owner, field_keys[F_DICT]);
    if (!state)
        return NULL;
    if (!PyDict_CheckExact(state)) {
        Py_DECREF(state);
        PyErr_SetString(PyExc_TypeError, "cold observer requires an ordinary owner dictionary");
        return NULL;
    }
    code = dict_field(state, F_CODE);
    executions = dict_field(state, F_EXECUTIONS);
    sampler = dict_field(state, F_SAMPLER);
    word_reader = dict_field(state, F_WORD_READER);
    if (!code || !PyBytes_CheckExact(code) || !executions || !PyDict_Check(executions) ||
        !sampler || !word_reader || dict_field(state, F_CPU) != reader->cpu) {
        Py_DECREF(state);
        PyErr_SetString(PyExc_RuntimeError, "cold observer owner profile is incomplete");
        return NULL;
    }
    self->reader = Py_NewRef((PyObject *)reader);
    self->interesting = Py_NewRef(interesting);
    self->state = state;
    self->code = Py_NewRef(code);
    self->executions = Py_NewRef(executions);
    self->sampler = Py_NewRef(sampler);
    self->word_reader = Py_NewRef(word_reader);
    Py_RETURN_NONE;
}

static PyObject *cold_stats(ColdObserver *self, PyObject *unused)
{
    (void)unused;
    return Py_BuildValue("{s:K,s:K}", "fast", (unsigned long long)self->fast_calls,
        "reference", (unsigned long long)self->reference_calls);
}

static int cold_traverse(ColdObserver *self, visitproc visit, void *arg)
{
    Py_VISIT(self->owner);
    Py_VISIT(self->original);
    Py_VISIT(self->reader);
    Py_VISIT(self->interesting);
    Py_VISIT(self->state);
    Py_VISIT(self->code);
    Py_VISIT(self->executions);
    Py_VISIT(self->sampler);
    Py_VISIT(self->word_reader);
    return 0;
}

static int cold_clear(ColdObserver *self)
{
    Py_CLEAR(self->owner);
    Py_CLEAR(self->original);
    Py_CLEAR(self->reader);
    Py_CLEAR(self->interesting);
    Py_CLEAR(self->state);
    Py_CLEAR(self->code);
    Py_CLEAR(self->executions);
    Py_CLEAR(self->sampler);
    Py_CLEAR(self->word_reader);
    return 0;
}

static void cold_dealloc(ColdObserver *self)
{
    PyObject_GC_UnTrack(self);
    cold_clear(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyMethodDef cold_methods[] = {
    {"enable", (PyCFunction)cold_enable, METH_VARARGS, "Enable the explicitly qualified raw cold-observer profile."},
    {"stats", (PyCFunction)cold_stats, METH_NOARGS, "Return observer dispatch counts, not guest acceptance."},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject ColdObserverType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_npu_read_api.ColdObserver",
    .tp_basicsize = sizeof(ColdObserver),
    .tp_dealloc = (destructor)cold_dealloc,
    .tp_call = cold_call,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)cold_traverse,
    .tp_clear = (inquiry)cold_clear,
    .tp_methods = cold_methods,
    .tp_init = (initproc)cold_init,
    .tp_new = PyType_GenericNew,
};

static PyObject *block_reference(BlockObserver *self, PyObject *args, PyObject *kwargs)
{
    self->reference_calls++;
    return PyObject_Call(self->original, args, kwargs);
}

static PyObject *block_call(PyObject *object, PyObject *args, PyObject *kwargs)
{
    BlockObserver *self = (BlockObserver *)object;
    Reader *reader;
    PyObject *state, *cache, *key, *names, *counts, *minimum;
    unsigned long long old_sp;
    uint64_t sp = 0;
    int status;

    if (!self->owner || !self->original || !self->reader) {
        PyErr_SetString(PyExc_RuntimeError, "block observer is not initialized");
        return NULL;
    }
    if ((kwargs && PyDict_Size(kwargs)) || PyTuple_GET_SIZE(args) != 4)
        return block_reference(self, args, kwargs);
    state = PyObject_GetAttr(self->owner, field_keys[F_DICT]);
    if (!state)
        return NULL;
    status = state == self->state;
    Py_DECREF(state);
    if (!status)
        return block_reference(self, args, kwargs);
    state = self->state;
    if (dict_field(state, F_RPC_ACTIVE) == Py_False) {
        self->inactive_calls++;
        Py_RETURN_NONE;
    }
    reader = (Reader *)self->reader;
    if (dict_field(state, F_RPC_ACTIVE) != Py_True || PyTuple_GET_ITEM(args, 0) != reader->cpu ||
        dict_field(state, F_CPU) != reader->cpu || !PyLong_CheckExact(PyTuple_GET_ITEM(args, 1)) ||
        !PyLong_CheckExact(PyTuple_GET_ITEM(args, 2)))
        return block_reference(self, args, kwargs);
    cache = dict_field(state, F_BLOCK_CACHE);
    if (!cache || !PyDict_CheckExact(cache))
        return block_reference(self, args, kwargs);
    key = PyTuple_Pack(2, PyTuple_GET_ITEM(args, 1), PyTuple_GET_ITEM(args, 2));
    if (!key)
        return NULL;
    names = PyDict_GetItemWithError(cache, key);
    Py_DECREF(key);
    if (PyErr_Occurred())
        return NULL;
    /* Cache misses retain the reference's complete byte/range/forbidden-PC checks. */
    if (!names || !PyTuple_CheckExact(names))
        return block_reference(self, args, kwargs);
    counts = dict_field(state, F_COUNTS);
    minimum = dict_field(state, F_MIN_SP);
    if (!counts || (PyObject *)Py_TYPE(counts) != self->counter_type || !minimum || !PyLong_CheckExact(minimum))
        return block_reference(self, args, kwargs);
    old_sp = PyLong_AsUnsignedLongLong(minimum);
    if (PyErr_Occurred()) {
        if (!PyErr_ExceptionMatches(PyExc_OverflowError))
            return NULL;
        PyErr_Clear();
        return block_reference(self, args, kwargs);
    }
    for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(names); i++)
        if (!PyUnicode_CheckExact(PyTuple_GET_ITEM(names, i)))
            return block_reference(self, args, kwargs);
    if (!check_reader(reader))
        return NULL;
    self->fast_calls++;
    if (!increment_item(counts, field_keys[F_BLOCKS]))
        return NULL;
    status = reader->read(reader->handle, UC_RISCV_REG_SP, &sp);
    if (status)
        return backend_error(reader, status, UC_RISCV_REG_SP, 1);
    if (sp < old_sp) {
        PyObject *value = PyLong_FromUnsignedLongLong(sp);
        if (!value)
            return NULL;
        status = PyDict_SetItem(state, field_keys[F_MIN_SP], value);
        Py_DECREF(value);
        if (status < 0)
            return NULL;
    }
    for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(names); i++)
        if (!increment_item(counts, PyTuple_GET_ITEM(names, i)))
            return NULL;
    Py_RETURN_NONE;
}

static int block_init(BlockObserver *self, PyObject *args, PyObject *kwargs)
{
    PyObject *owner, *original, *state, *executions;
    Reader *reader;
    static char *names[] = {"owner", "original", "reader", NULL};

    if (self->owner) {
        PyErr_SetString(PyExc_RuntimeError, "block observer cannot be rebound");
        return -1;
    }
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOO!", names, &owner, &original, &ReaderType, &reader))
        return -1;
    if (!PyCallable_Check(original) || !check_reader(reader)) {
        if (!PyErr_Occurred())
            PyErr_SetString(PyExc_TypeError, "block observer requires the reference callback");
        return -1;
    }
    state = PyObject_GetAttr(owner, field_keys[F_DICT]);
    if (!state)
        return -1;
    executions = PyDict_CheckExact(state) ? dict_field(state, F_EXECUTIONS) : NULL;
    if (!executions || !PyDict_Check(executions) || dict_field(state, F_CPU) != reader->cpu) {
        Py_DECREF(state);
        PyErr_SetString(PyExc_RuntimeError, "block observer owner/engine profile differs");
        return -1;
    }
    self->owner = Py_NewRef(owner);
    self->original = Py_NewRef(original);
    self->reader = Py_NewRef((PyObject *)reader);
    self->state = state;
    self->counter_type = Py_NewRef((PyObject *)Py_TYPE(executions));
    return 0;
}

static PyObject *block_stats(BlockObserver *self, PyObject *unused)
{
    (void)unused;
    return Py_BuildValue("{s:K,s:K,s:K}", "fast", (unsigned long long)self->fast_calls,
        "reference", (unsigned long long)self->reference_calls, "inactive", (unsigned long long)self->inactive_calls);
}

static int block_traverse(BlockObserver *self, visitproc visit, void *arg)
{
    Py_VISIT(self->owner);
    Py_VISIT(self->original);
    Py_VISIT(self->reader);
    Py_VISIT(self->state);
    Py_VISIT(self->counter_type);
    return 0;
}

static int block_clear(BlockObserver *self)
{
    Py_CLEAR(self->owner);
    Py_CLEAR(self->original);
    Py_CLEAR(self->reader);
    Py_CLEAR(self->state);
    Py_CLEAR(self->counter_type);
    return 0;
}

static void block_dealloc(BlockObserver *self)
{
    PyObject_GC_UnTrack(self);
    block_clear(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyMethodDef block_methods[] = {
    {"stats", (PyCFunction)block_stats, METH_NOARGS, "Return block dispatch counts, not NPU acceptance."},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject BlockObserverType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_npu_read_api.BlockObserver",
    .tp_basicsize = sizeof(BlockObserver),
    .tp_dealloc = (destructor)block_dealloc,
    .tp_call = block_call,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)block_traverse,
    .tp_clear = (inquiry)block_clear,
    .tp_methods = block_methods,
    .tp_init = (initproc)block_init,
    .tp_new = PyType_GenericNew,
};

static PyObject *reader_original(Reader *self, void *unused)
{
    (void)unused;
    if (!self->original) {
        PyErr_SetString(PyExc_RuntimeError, "native reader is not initialized");
        return NULL;
    }
    return Py_NewRef(self->original);
}

static int reader_init(Reader *self, PyObject *args, PyObject *kwargs)
{
    PyObject *cpu, *original, *error_type, *registers;
    unsigned long long read_address, batch_address, memory_address = 0;
    void *handle;
    static char *names[] = {"cpu", "original", "error_type", "read_address", "batch_address", "registers",
                            "memory_address", NULL};

    if (self->cpu) {
        PyErr_SetString(PyExc_RuntimeError, "native reader cannot be rebound");
        return -1;
    }
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOOKKO|K", names, &cpu, &original,
                                    &error_type, &read_address, &batch_address, &registers, &memory_address))
        return -1;
    if (!read_address || !batch_address || !PyCallable_Check(original) ||
        !PyExceptionClass_Check(error_type) || !PyTuple_Check(registers) || PyTuple_GET_SIZE(registers) != 3) {
        PyErr_SetString(PyExc_ValueError, "native reader requires reviewed C API addresses, original reader and three CSR IDs");
        return -1;
    }
    handle = engine_handle(cpu);
    if (!handle)
        return -1;
    for (int i = 0; i < 3; i++) {
        long value = PyLong_AsLong(PyTuple_GET_ITEM(registers, i));
        if (PyErr_Occurred())
            return -1;
        if (value < INT_MIN || value > INT_MAX) {
            PyErr_SetString(PyExc_OverflowError, "CSR register ID is outside C int range");
            return -1;
        }
        self->registers[i] = (int)value;
    }
    self->cpu = Py_NewRef(cpu);
    self->original = Py_NewRef(original);
    self->error_type = Py_NewRef(error_type);
    self->handle = handle;
    self->thread = PyThread_get_thread_ident();
    self->read = (read_register_fn)(uintptr_t)read_address;
    self->batch = (read_batch_fn)(uintptr_t)batch_address;
    self->memory = (read_memory_fn)(uintptr_t)memory_address;
    return 0;
}

static int reader_traverse(Reader *self, visitproc visit, void *arg)
{
    Py_VISIT(self->cpu);
    Py_VISIT(self->original);
    Py_VISIT(self->error_type);
    return 0;
}

static int reader_clear(Reader *self)
{
    Py_CLEAR(self->cpu);
    Py_CLEAR(self->original);
    Py_CLEAR(self->error_type);
    return 0;
}

static void reader_dealloc(Reader *self)
{
    PyObject_GC_UnTrack(self);
    reader_clear(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyMethodDef reader_methods[] = {
    {"csrs", (PyCFunction)reader_csrs, METH_NOARGS, "Read three fresh CSRs using the loaded Unicorn C API."},
    {"u32", (PyCFunction)reader_u32, METH_O, "Read a fresh little-endian word using the loaded Unicorn memory API."},
    {"bind_emulator", (PyCFunction)reader_bind_emulator, METH_O, "Bind the reviewed per-engine native emulation API once."},
    {"emulate", _PyCFunction_CAST(reader_emulate), METH_VARARGS | METH_KEYWORDS, "Run the same bounded native emulator while retaining the calling GIL."},
    {NULL, NULL, 0, NULL}
};

static PyGetSetDef reader_getset[] = {
    {"original_read", (getter)reader_original, NULL, "Original Python reader for opt-out.", NULL},
    {NULL, NULL, NULL, NULL, NULL}
};

static PyTypeObject ReaderType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_npu_read_api.Reader",
    .tp_basicsize = sizeof(Reader),
    .tp_dealloc = (destructor)reader_dealloc,
    .tp_call = reader_call,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)reader_traverse,
    .tp_clear = (inquiry)reader_clear,
    .tp_methods = reader_methods,
    .tp_getset = reader_getset,
    .tp_init = (initproc)reader_init,
    .tp_new = PyType_GenericNew,
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_npu_read_api",
    .m_doc = "Per-engine/thread bridge to the same loaded Unicorn register and memory read APIs.",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit__npu_read_api(void)
{
    PyObject *result;

    for (int i = 0; i < F_COUNT; i++) {
        if (!field_keys[i])
            field_keys[i] = PyUnicode_InternFromString(field_names[i]);
        if (!field_keys[i])
            return NULL;
    }
    if (PyType_Ready(&ReaderType) < 0 || PyType_Ready(&ColdObserverType) < 0 || PyType_Ready(&BlockObserverType) < 0)
        return NULL;
    result = PyModule_Create(&module);
    if (!result)
        return NULL;
    if (PyModule_AddObjectRef(result, "Reader", (PyObject *)&ReaderType) < 0) {
        Py_DECREF(result);
        return NULL;
    }
    if (PyModule_AddIntConstant(result, "API_VERSION", 2) < 0) {
        Py_DECREF(result);
        return NULL;
    }
    if (PyModule_AddObjectRef(result, "ColdObserver", (PyObject *)&ColdObserverType) < 0 ||
        PyModule_AddObjectRef(result, "BlockObserver", (PyObject *)&BlockObserverType) < 0 ||
        PyModule_AddIntConstant(result, "COLD_OBSERVER_API_VERSION", 3) < 0 ||
        PyModule_AddIntConstant(result, "COLD_OBSERVER_PC_REG", UC_RISCV_REG_PC) < 0 ||
        PyModule_AddIntConstant(result, "COLD_OBSERVER_X0_REG", UC_RISCV_REG_X0) < 0) {
        Py_DECREF(result);
        return NULL;
    }
    return result;
}
