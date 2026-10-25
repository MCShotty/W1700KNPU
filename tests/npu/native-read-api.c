#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <limits.h>
#include <stdint.h>
#include <unicorn/unicorn.h>

typedef uc_err (*read_register_fn)(uc_engine *, int, void *);
typedef uc_err (*read_batch_fn)(uc_engine *, const int *, void **, int);
typedef uc_err (*read_memory_fn)(uc_engine *, uint64_t, void *, uint64_t);

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
    int registers[3];
} Reader;

static void *engine_handle(PyObject *cpu)
{
    PyObject *handle = PyObject_GetAttrString(cpu, "_uch");
    PyObject *value;
    void *result;

    if (!handle)
        return NULL;
    value = PyObject_GetAttrString(handle, "value");
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

    if (PyType_Ready(&ReaderType) < 0)
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
    return result;
}
