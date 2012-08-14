%module testlal

%{
#define SWIG_FILE_WITH_INIT
#include <string.h>
#include <lal/LALAtomicDatatypes.h>
#include <lal/LALDatatypes.h>
#include <lal/AVFactories.h>
#include <lal/VectorOps.h>
#include <numpy/arrayobject.h>
#include <lal/ComplexFFT.h>
#include <lal/XLALError.h>
%}

%ignore XLALCOMPLEX8VectorFFT;
%ignore XLALSSVectorMultiply;
%ignore XLALCreateREAL4Vector;

// Seems we must manually include <exception.i> before importing
// <lal/lalswig.i>.  Might be a bug in lalswig, or might just be
// unavoidable given that we %import rather than %include the
// lal wrappings.
%include <exception.i>
%import <lal/lalswig.i>

%begin %{
#define SWIG_TYPE_TABLE swiglal
%}

// We define global variables and the functions that will initialize
// them in the header portion of our interface file; the initialization
// functions are actually called in the %init section.

%header %{
// The next three global variables hold handles to the three basic
// PyCBC data types that can be used by C-API functions to create
// new instances of these objects when needed as return types by
// various typemaps below.  They can also be used by typemaps to check
// that input variables are in fact instances of the intended input
// types. These three are initialized by the function import_pycbc().
PyObject *CBC_Arr = NULL;
PyObject *CBC_TS = NULL;
PyObject *CBC_FS = NULL;
// The next global variables is simply an empty tuple that it is
// useful to have around for the various PyCBC constructors. The 'arg'
// parameter cannot be NULL, but for safety we always call with only
// keyword arguments.  Hence the empty tuple to be reused as the 'arg'
// parameter of constructors.  This is initialized in init_etuple().
PyObject *EmptyTuple = NULL;

// This code imports from pycbc.types the three basic
// datatypes of Array, TimeSeries, and FrequencySeries. They are
// imported as CBC_Arr, CBC_TS, and CBC_FS.
void import_pycbc(void){
  PyObject *CBC_ArrName, *CBC_TSName, *CBC_FSName;
  PyObject *CBC_TypesModule, *CBC_FromList, *CBC_Globals;

  CBC_ArrName = NULL;
  CBC_TSName = NULL;
  CBC_FSName = NULL;
  CBC_FromList = NULL;
  CBC_TypesModule = NULL;

  CBC_ArrName = PyString_FromString("Array");
  CBC_TSName = PyString_FromString("TimeSeries");
  CBC_FSName = PyString_FromString("FrequencySeries");
  if (!CBC_ArrName || !CBC_TSName || !CBC_FSName) goto fail;
  CBC_FromList = PyList_New(0);
  if (!CBC_FromList) goto fail;
  if (PyList_Append(CBC_FromList,CBC_ArrName)) goto fail;
  if (PyList_Append(CBC_FromList,CBC_TSName)) goto fail;
  if (PyList_Append(CBC_FromList,CBC_FSName)) goto fail;


  // Now we're ready to import the actual pycbc.types module

  // We only attempt to access the globals(), and just use NULL
  // where locals() would go in the module import, because
  // __import__ is documented as ignoring the locals() argument
  // and using globals only to determine package context. For
  // the same reason we explicitly create our global variables and
  // load them, rather than relying on typemaps to look them up in
  // either globals() or locals() (which would be slower, as well).

  CBC_Globals = PyEval_GetGlobals();
  Py_XINCREF(CBC_Globals); // Because we've just borrowed a reference
  CBC_TypesModule = PyImport_ImportModuleEx("pycbc.types",CBC_Globals,
					    NULL,CBC_FromList);
  Py_XDECREF(CBC_Globals);
  if (!CBC_TypesModule) goto fail;

  CBC_Arr = PyObject_GetAttr(CBC_TypesModule,CBC_ArrName);
  CBC_TS = PyObject_GetAttr(CBC_TypesModule,CBC_TSName);
  CBC_FS = PyObject_GetAttr(CBC_TypesModule,CBC_FSName);

  if (!CBC_Arr || !CBC_TS || !CBC_FS) goto fail;

  Py_DECREF(CBC_FromList);
  Py_DECREF(CBC_ArrName);
  Py_DECREF(CBC_TSName);
  Py_DECREF(CBC_FSName);
  Py_DECREF(CBC_TypesModule);

  return;

 fail:
  Py_XDECREF(CBC_Arr);
  Py_XDECREF(CBC_TS);
  Py_XDECREF(CBC_FS);
  Py_XDECREF(CBC_FromList);
  Py_XDECREF(CBC_ArrName);
  Py_XDECREF(CBC_TSName);
  Py_XDECREF(CBC_FSName);
  Py_XDECREF(CBC_TypesModule);
  PyErr_SetString(PyExc_ImportError,"Error importing 'pycbc.types'");
  PyErr_Print();
  return;
}

void init_etuple(void) {
  EmptyTuple = PyTuple_New(0);
  if (!EmptyTuple) {
    PyErr_SetString(PyExc_RuntimeError,"Error creating empty tuple for internal use");
    PyErr_Print();
    return;
  }
  return;
}

%}

%init {
  import_array();
  import_pycbc();
  init_etuple();
}

/*

Fragments

The next section contains several SWIG typemap
fragments, that are reused in several of the actual
typemaps.  They are essentially all either struct or
function definitions that are used or called when
sanity-checking the results of a typemap conversion
between C and Python.

*/

// Force inclusion of SWIG_From_int
// This is possibly a bug in the swiglal wrappings?

%fragment("SWIG_From_int");


%fragment("GenericVector","header") {
// The following struct is just so we can
// sanity check some output vectors without
// knowing exactly what datatype they are.
// This struct should not be SWIG-wrapped,
// nor used outside of the functions defined
// elsewhere in this file.
typedef struct {
  UINT4 length;
  void *data;
} GenericVector;

}

%fragment("GenericTS","header",fragment="GenericVector") {
// The following struct is just so we can
// sanity check some output time series without
// knowing exactly what datatype they are.
// This struct should not be SWIG-wrapped,
// nor used outside of the functions defined
// elsewhere in this file.
typedef struct {
  CHAR          name[LALNameLength];
  LIGOTimeGPS   epoch;
  REAL8         deltaT;
  REAL8         f0;
  LALUnit       sampleUnits;
  GenericVector *data;
} GenericTS;

}

%fragment("GenericFS","header",fragment="GenericVector") {
// The following struct is just so we can
// sanity check some output freq. series without
// knowing exactly what datatype they are.
// This struct should not be SWIG-wrapped,
// nor used outside of the functions defined
// elsewhere in this file.
typedef struct {
  CHAR          name[LALNameLength];
  LIGOTimeGPS   epoch;
  REAL8         f0;
  REAL8         deltaF;
  LALUnit       sampleUnits;
  GenericVector *data;
} GenericFS;

}

// The following fragment is used by any of the "ARGOUT" types to build
// a (possible) tuple of return values, since only in this case can
// there be more than one (that we must worry about).  It doesn't care
// at all what kind of Python objects its two inputs represent; the
// first is whatever output has been built up to now, and the second is
// the new value to add.  This is based on the example code with the
// SWIG documentation, except unlike that documentation we check the C
// functions we call for success.

%fragment("BuildReturnFromValue","header") {
  PyObject *BuildReturnFromValue(PyObject *CurrReturn, PyObject *value){
    PyObject *o1 = NULL, *o2 = NULL, *NewReturn = NULL;

    if (!CurrReturn){
      NewReturn = value;
    } else if (CurrReturn == Py_None) {
      Py_DECREF(Py_None);
      NewReturn = value;
    } else {
      if (!PyTuple_Check(CurrReturn)) {
	// We have exactly one thing in the current return already,
	// so we save it, make a new tuple, and make what was there
	// into a single-element tuple.
	o1 = CurrReturn;
	CurrReturn = PyTuple_New(1);
	if (!(CurrReturn)) {
	  PyErr_SetString(PyExc_RuntimeError,
			  "Error building return tuple");
	  Py_DECREF(value); // When we return, we'll got right to SWIG_fail
	  Py_DECREF(o1);
	  return NULL;
	}
	// Note: PyTuple_SetItem steals the reference to o1, so
	// we don't DECREF it.
	if (PyTuple_SetItem(CurrReturn,0,o1)) {
	  PyErr_SetString(PyExc_RuntimeError,
			  "Error building return tuple");
	  Py_DECREF(value);
	  Py_DECREF(CurrReturn);
	  return NULL;
	}
      }
      // If we get here CurrReturn is a tuple of previous returns
      o2 = PyTuple_New(1);
      if (!o2) {
	PyErr_SetString(PyExc_RuntimeError,
			"Error building return tuple");
	Py_DECREF(value);
	Py_DECREF(CurrReturn);
	return NULL;
      }
      // Again, PyTuple_SetItem steals a reference to value, so no need
      // to DECREF it.
      if(PyTuple_SetItem(o2,0,value)){
	Py_DECREF(CurrReturn);
	Py_DECREF(o2);
	return NULL;
      }
      // Now each of CurrReturn and o2 are tuples.  We want to
      // return their concatentation, and clean up if that fails
      NewReturn = PySequence_concat(CurrReturn,o2);
      if (!NewReturn) {
	Py_DECREF(CurrReturn);
	Py_DECREF(o2);
	return NULL;
      }
      Py_DECREF(CurrReturn);
      Py_DECREF(o2);
    }
    return NewReturn;
  }
}

%fragment("MarshallInputVector","header",fragment="GenericVector") {
  GenericVector *MarshallInputVector(PyObject *obj, const int numpy_type, const char *objname) {
    GenericVector *returnptr;
    PyObject *dataobj, *tmpobj;

    tmpobj = PyObject_GetAttrString(obj,"lal");

    // We explicitly access the 'lal' attribute of the argument, to force it onto
    // the CPU (if it was on the GPU and the current scheme is CPU) or to raise an
    // exception (if the current scheme is GPU).

    // We should have a 'lal' attribute, and it should point back to our argument, or
    // there's a problem.

    if (tmpobj != obj) {
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s' has no 'lal' attribute---it is not an instance of pycbc.types.Array",
		   objname);
      Py_XDECREF(tmpobj);
      return NULL;
    }

    // If we get here, it means that the lal property did behave as expected, so to avoid
    // an ever-increasing refcount, we must now decrement it:

    Py_DECREF(tmpobj);

    if (PyObject_IsInstance(obj,CBC_Arr) !=1){
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s' must be an instance of pycbc.types.Array or subclass", objname);
      return NULL;
    }

    dataobj = PyObject_GetAttrString(obj,"_data");
    if (!dataobj){
      PyErr_Format(PyExc_TypeError,
		   "Could not get _data property of argument '%s'", objname);
      return NULL;
    }
    if (!PyArray_Check(dataobj)){
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s._data' must be a numpy array", objname);
      return NULL;
    }
    if (!(PyArray_ISCARRAY((PyArrayObject *) dataobj)
	  || PyArray_ISCARRAY_RO((PyArrayObject *) dataobj)) ){
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s._data' is not C-order contiguous",objname);
      return NULL;
    }
    if ( PyArray_NDIM((PyArrayObject *) dataobj) != 1) {
      PyErr_Format(PyExc_ValueError,
		   "Argument '%s._data' is not one-dimensional",objname);
      return NULL;
    }
    if (PyArray_TYPE((PyArrayObject *) dataobj) != numpy_type) {
      PyErr_Format(PyExc_ValueError,
		   "Argument '%s._data' has wrong dtype for corresponding LAL vector",objname);
      return NULL;
    }

    // Assemble our return object, which is a GenericVector.  If LAL should ever change
    // its definitions of Vectors so that different types change by more than underlying datatypes,
    // this would all have to be redone into a case statement based on the dtype.

    returnptr = (GenericVector *) calloc(1,sizeof(GenericVector));
    if (!returnptr) {
      PyErr_Format(PyExc_MemoryError,
		   "Could not allocate temporary Vector for argument '%s'",objname);
      return NULL;
    }
    returnptr->data = PyArray_DATA(dataobj);
    returnptr->length = (UINT4) PyArray_DIM(dataobj,0);

    return returnptr;
  }
}

%fragment("MarshallOutputVector","header",fragment="GenericVector") {
  PyObject *MarshallOutputVector(GenericVector *vect, const int numpy_type) {
    PyObject *result, *dataobj, *dtypeobj, *copybool, *constrdict;


    if (!(vect)) {
      PyErr_SetString(PyExc_ValueError,"Unexpected null vector returned from function");
      return NULL;
    }
    if ( (vect->length) &&  !(vect->data) ) {
      PyErr_SetString(PyExc_ValueError,"Null data pointer returned for non-zero length array");
      return NULL;
    }

    constrdict = PyDict_New();
    if (!constrdict) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create dictionary for return value constructor");
      return NULL;
    }

    npy_intp dimensions[1];
    dimensions[0] = (npy_intp) vect->length;
    dataobj = PyArray_SimpleNewFromData(1,dimensions,numpy_type,(void *) vect->data);
    if (!dataobj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output data object");
      Py_DECREF(constrdict); // Dict still empty, so just delete
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"initial_array",dataobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add data object to cosntructor dict");
      Py_DECREF(constrdict); // Dict still empty, so just delete
      Py_DECREF(dataobj);
      return NULL;
    }

    dtypeobj = (PyObject *) PyArray_DescrFromType(numpy_type);
    if (!dtypeobj){
      PyErr_SetString(PyExc_RuntimeError,"Could not create output dtype object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"dtype",dtypeobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add dtype object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      return NULL;
    }

    Py_INCREF(Py_False);
    copybool = Py_False;
    if (PyDict_SetItemString(constrdict,"copy",copybool)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add copy object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      return NULL;
    }

    result = PyObject_Call(CBC_Arr,EmptyTuple,constrdict);
    if (!result) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create new instance of pycbc.types.Array");
    }
    // We don't need to do anything else for that last failure, as we'll be returning NULL
    // anyway and we have to do the same cleanup
    PyDict_Clear(constrdict);
    Py_DECREF(constrdict);
    Py_DECREF(dataobj);
    Py_DECREF(dtypeobj);
    Py_DECREF(copybool);

    return result;
  }
 }

%fragment("BuildArgoutVector","header",
	  fragment="BuildReturnFromValue",fragment="MarshallOutputVector") {};

%fragment("MarshallInputTS","header",fragment="GenericTS") {
  GenericTS *MarshallInputTS(PyObject *obj, const int numpy_type, const char *objname) {
    GenericVector *vecptr;
    GenericTS *returnptr;
    PyObject *dataobj, *tmpobj, *nameobj;
    char *NameString, BlankString[1] = '\0';
    double f0, deltaT;
    LALUnit *sampleUnits_ptr;
    LIGOTimeGPS *epoch_ptr;
    int i;

    tmpobj = PyObject_GetAttrString(obj,"lal");

    // We explicitly access the 'lal' attribute of the argument, to force it onto
    // the CPU (if it was on the GPU and the current scheme is CPU) or to raise an
    // exception (if the current scheme is GPU).

    // We should have a 'lal' attribute, and it should point back to our argument, or
    // there's a problem.

    if (tmpobj != obj) {
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s' has no 'lal' attribute---it is not an instance of pycbc.types.TimeSeries",
		   objname);
      Py_XDECREF(tmpobj);
      return NULL;
    }

    // If we get here, it means that the lal property did behave as expected, so to avoid
    // an ever-increasing refcount, we must now decrement it:

    Py_DECREF(tmpobj);

    if (PyObject_IsInstance(obj,CBC_TS) !=1){
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s' must be an instance of pycbc.types.TimeSeries or subclass", objname);
      return NULL;
    }

    // First, marshall everything for the numpy array that is "self._data"

    dataobj = PyObject_GetAttrString(obj,"_data");
    if (!dataobj){
      PyErr_Format(PyExc_TypeError,
		   "Could not get _data property of argument '%s'", objname);
      return NULL;
    }
    if (!PyArray_Check(dataobj)){
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s._data' must be a numpy array", objname);
      return NULL;
    }
    if (!(PyArray_ISCARRAY((PyArrayObject *) dataobj)
	  || PyArray_ISCARRAY_RO((PyArrayObject *) dataobj)) ){
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s._data' is not C-order contiguous",objname);
      return NULL;
    }
    if ( PyArray_NDIM((PyArrayObject *) dataobj) != 1) {
      PyErr_Format(PyExc_ValueError,
		   "Argument '%s._data' is not one-dimensional",objname);
      return NULL;
    }
    if (PyArray_TYPE((PyArrayObject *) dataobj) != numpy_type) {
      PyErr_Format(PyExc_ValueError,
		   "Argument '%s._data' has wrong dtype for corresponding LAL vector",objname);
      return NULL;
    }

    // Start assembling our return object, which is a GenericTS.  If LAL should ever change
    // its definitions of TS so that different types change by more than underlying datatypes,
    // this would all have to be redone into a case statement based on the dtype.

    vecptr = (GenericVector *) calloc(1,sizeof(GenericVector));
    returnptr = (GenericTS *) calloc(1,sizeof(GenericTimeSeries));
    if (!returnptr || !vecptr) {
      PyErr_Format(PyExc_MemoryError,
		   "Could not allocate temporary TimeSeries for argument '%s'",objname);
      if (vecptr) free(vecptr);
      if (returnptr) free(returnptr);
      return NULL;
    }
    vecptr->data = PyArray_DATA(dataobj);
    vecptr->length = (UINT4) PyArray_DIM(dataobj,0);
    returnptr->data = vecptr;

    // Next, marshall all of the other pieces of a TimeSeries.  Our PyCBC types
    // don't necessarily have all of these set, in which case we put in default
    // values to pass through to LAL (which should not have these as garbage or missing).

    // First, the name, one of the things that may be missing.  This is actually one of the
    // trickiest things to deal with, because the Python C-API function PyString_AsString()
    // returns a pointer to its internal buffer, which must not be modified or deallocated.
    // To simplify passing *back* this argument, we always create a new string for our name,
    // and if our object passed in had the name string set it will get back a new string
    // with the same value (rather than figuring out whether it was modfied in place or not).

    if (PyObject_HasAttrString(obj,"_name")){
      tmpobj = PyObject_GetAttrString(obj,"_name");
      if (!tmpobj || !PyString_Check(tmpobj)) {
	Py_XDECREF(tmpobj);
	PyErr_Format(PyExc_TypeError,"Argument '%s._name' exists but is not a valid Python string",objname);
	return NULL;
      }
      NameString = PyString_AsString(tmpobj);
      // The following cannot deallocate the string, because the python object obj
      // holds a reference to the 'name' attribute, and the C-API function call holds
      // a reference to obj.
      Py_XDECREF(tmpobj);
    } else {
      NameString = BlankName;
    }
    strncpy(returnptr->name,NameString,LALNameLength-1);
    returnptr->name[LALNameLength-1] = '\0';

    // Next, epoch, which is required:

    tmpobj = PyObject_GetAttrString(obj,"_epoch");
    if (!tmpobj ||
	(SWIG_ConvertPtr(tmpobj,(void **) &epoch_ptr,$descriptor(LIGOTimeGPS *),SWIG_POINTER_EXCEPTION) == -1)){
      Py_XDECREF(tmpobj);
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s._epoch' does not exist or is not an instance of LIGOTimeGPS",objname);
      return NULL;
    }
    returnptr->epoch.gpsSeconds = epoch->gpsSeconds;
    returnptr->epoch.gpsNanoSeconds = epoch->gpsNanoSeconds;
    Py_DECREF(tmpobj);

    // Next, delta_t, which is required:

    tmpobj = PyObject_GetAttrString(obj,"_delta_t");
    if (!tmpobj || !PyFloat_Check(tmpobj)){
      Py_XDECREF(tmpobj);
      PyErr_Format(PyExc_TypeError,
		   "Argument '%s._delta_t' does not exist or is not a valid Python double",objname);
      return NULL;
    }
    // We use the macro form below---which doesn't check for errors--because
    // we've already checked that we have a float.
    returnptr->deltaT = PyFloat_AS_DOUBLE(tmpobj);
    Py_DECREF(tmpobj);

    // Next, f0, which is optional:

    if (PyObject_HasAttrString(obj,"_f0")) {
      tmpobj = PyObject_GetAttrString(obj,"_f0");
      if (!tmpobj || !PyFloat_Check(tmpobj)){
	Py_XDECREF(tmpobj);
	PyErr_Format(PyExc_TypeError,
		     "Argument '%s._f0' exists but is not a valid Python double",objname);
	return NULL;
      }
      // We use the macro form below---which doesn't check for errors--because
      // we've already checked that we have a float.
      returnptr->f0 = PyFloat_AS_DOUBLE(tmpobj);
      Py_DECREF(tmpobj);
    } else {
      returnptr->f0 = 0.0;
    }

    // Finally, sampleUnits, which is optional:

    if (PyObject_HasAttrString(obj,"_sample_units")) {
      tmpobj = PyObject_GetAttrString(obj,"_sample_units");
      if (!tmpobj ||
	  (SWIG_ConvertPtr(tmpobj,(void **) &sampleUnits_ptr,$descriptor(LALUnit *),SWIG_POINTER_EXCEPTION) == -1)){
	Py_XDECREF(tmpobj);
	PyErr_Format(PyExc_TypeError,
		     "Argument '%s._sample_units' exists but is not a valid LALUnit object",objname);
	return NULL;
      }
      returnptr->sampleUnits.powerOfTen = sampleUnits_ptr->powerOfTen;
      for (i=0;i<LALNumUnits;i++){
	returnptr->sampleUnits.unitNumerator[i] = sampleUnits_ptr->unitNumerator[i];
	returnptr->sampleUnits.unitDenominatorMinusOne[i] = sampleUnits_ptr->unitDenominatorMinusOne[i];
      }
      Py_DECREF(tmpobj);
    } else {
      returnptr->sampleUnits = lalDimensionlessUnit;
    }

    return returnptr;
  }
}

%fragment("MarshallOutputTS","header",fragment="GenericTS") {
  PyObject *MarshallOutputVector(GenericTS *ts, const int numpy_type) {
    PyObject *result, *dataobj, *dtypeobj, *copybool, *constrdict;
    PyObject *f0obj, *epochobj, *delta_tobj, *nameobj, *unitsobj;
    LALUnit *sampleUnits_ptr;
    LIGOTimeGPS *epoch_ptr;
    int i;

    if (!(ts)) {
      PyErr_SetString(PyExc_ValueError,"Unexpected null time-series returned from function");
      return NULL;
    }
    if ( !(ts->data) ) {
      PyErr_SetString(PyExc_ValueError,"Time series output had empty data vector");
      return NULL;
    }
    if ( !(ts->data->data) &&  !(ts->data->length) ) {
      PyErr_SetString(PyExc_ValueError,
		      "Time series had null data pointer returned for non-zero length");
      return NULL;
    }

    constrdict = PyDict_New();
    if (!constrdict) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create dictionary for return value constructor");
      return NULL;
    }

    npy_intp dimensions[1];
    dimensions[0] = (npy_intp) vect->length;
    dataobj = PyArray_SimpleNewFromData(1,dimensions,numpy_type,(void *) vect->data);
    if (!dataobj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output data object");
      Py_DECREF(constrdict); // Dict still empty, so just delete
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"initial_array",dataobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add data object to cosntructor dict");
      Py_DECREF(constrdict); // Dict still empty, so just delete
      Py_DECREF(dataobj);
      return NULL;
    }

    dtypeobj = (PyObject *) PyArray_DescrFromType(numpy_type);
    if (!dtypeobj){
      PyErr_SetString(PyExc_RuntimeError,"Could not create output dtype object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"dtype",dtypeobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add dtype object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      return NULL;
    }

    Py_INCREF(Py_False);
    copybool = Py_False;
    if (PyDict_SetItemString(constrdict,"copy",copybool)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add copy object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      return NULL;
    }

    f0obj = PyFloat_FromDouble(ts->f0);
    if (!f0obj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output f0 object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"f0",f0obj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add f0 object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      return NULL;
    }

    epoch_ptr = calloc(1,sizeof(LIGOTimeGPS));
    if (!epoch_ptr) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output epoch object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      return NULL;
    }
    epoch_ptr->gpsSeconds = (ts->epoch).gpsSeconds;
    epoch_ptr->gpsNanoSeconds = (ts->epoch).gpsNanoSeconds;
    epochobj = SWIG_NewPointerObj((void *) epoch_ptr,$descriptor(LIGOTimeGPS *),SWIG_POINTER_OWN);
    if (!epochobj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output epoch object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      free(epoch_ptr);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"epoch",epochobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add epoch object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      return NULL;
    }

    delta_tobj = PyFloat_FromDouble(ts->deltaT);
    if (!delta_tobj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output delta_t object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"delta_t",delta_tobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add delta_t object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      Py_DECREF(delta_tobj);
      return NULL;
    }

    nameobj = PyString_FromStringAndSize(ts->name,LALNameLength);
    // If ts->name was NULL, then nameobj is uninitalized
    if (!nameobj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output name object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      Py_DECREF(delta_tobj);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"name",nameobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add name object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      Py_DECREF(delta_tobj);
      Py_DECREF(nameobj);
      return NULL;
    }

    sampleUnits_ptr = calloc(1,sizeof(LALUnit));
    if (!sampleUnits_ptr) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output sample_units object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      Py_DECREF(delta_tobj);
      Py_DECREF(nameobj);
      return NULL;
    }
    sampleUnits_ptr->powerOfTen = (ts->sampleUnits).powerOfTen;
    for (i=0; i < LALNumUnits; i++) {
      (sampleUnits_ptr->unitNumerator)[i] = (ts->sampleUnits).unitNumerator[i];
      (sampleUnits_ptr->unitDenominatorMinusOne)[i] = (ts->sampleUnits).unitDenominatorMinusOne[i];
    }
    unitsobj = SWIG_NewPointerObj((void *) sampleUnits_ptr,$descriptor(LALUnit *),SWIG_POINTER_OWN);
    if (!unitsobj) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create output sample_units object");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      Py_DECREF(delta_tobj);
      Py_DECREF(nameobj);
      free(sampleUnits_ptr);
      return NULL;
    }
    if (PyDict_SetItemString(constrdict,"sample_units",unitsobj)) {
      PyErr_SetString(PyExc_RuntimeError,"Could not add sample_units object to constructor dict");
      PyDict_Clear(constrdict);
      Py_DECREF(constrdict);
      Py_DECREF(dataobj);
      Py_DECREF(dtypeobj);
      Py_DECREF(copybool);
      Py_DECREF(f0obj);
      Py_DECREF(epochobj);
      Py_DECREF(delta_tobj);
      Py_DECREF(nameobj);
      Py_DECREF(unitsobj);
      return NULL;
    }

    result = PyObject_Call(CBC_TS,EmptyTuple,constrdict);
    if (!result) {
      PyErr_SetString(PyExc_RuntimeError,"Could not create new instance of pycbc.types.TimeSeries");
    }
    // We don't need to do anything else for that last failure, as we'll be returning NULL
    // anyway and we have to do the same cleanup
    PyDict_Clear(constrdict);
    Py_DECREF(constrdict);
    Py_DECREF(dataobj);
    Py_DECREF(dtypeobj);
    Py_DECREF(copybool);
    Py_DECREF(f0obj);
    Py_DECREF(epochobj);
    Py_DECREF(delta_tobj);
    Py_DECREF(nameobj);
    Py_DECREF(unitsobj);

    return result;
  }
 }

%fragment("MarshallArgoutTS","header",fragment="GenericTS") {
  int *MarshallArgoutVector(PyObject *argument, GenericTS *ts, const char *objname) {
    PyObject *f0obj, *epochobj, *delta_tobj, *nameobj, *unitsobj;
    LALUnit *sampleUnits_ptr;
    LIGOTimeGPS *epoch_ptr;
    int i;

    if (!(ts)) {
      PyErr_Format(PyExc_ValueError,
		   "Unexpected null time-series for argument '%s' after return",objname);
      return 1;
    }
    if ( !(ts->data) ) {
      PyErr_Format(PyExc_ValueError,
		   "Time series argument '%s' had empty data vector after return",objname);
      return 1;
    }
    if ( !(ts->data->data) &&  !(ts->data->length) ) {
      PyErr_Format(PyExc_ValueError,
		   "Time series argument '%s' had null data pointer returned for non-zero length",
		   objname);
      return 1;
    }

    // The _data attribute should have automatically been modified in place, as it was
    // wrapped from a numpy array.  For all other elements of the returned TimeSeries,
    // we check that the corresponding attribute (if it's optional) exists for
    // 'argument', and modify it in place.

    // The _f0 argument is optional
    if (PyObject_HasAttrString(argument,"_f0")){
	f0obj = PyFloat_FromDouble(ts->f0);
	if (!f0obj) {
	  PyErr_Format(PyExc_RuntimeError,
		       "Could not create output f0 object for '%s._f0'",objname);
	  return 1;
	}
	if (PyObject_SetAttrString(argument,"_f0",f0obj) == -1) {
	  PyErr_Format(PyExc_RuntimeError,
		       "Could not modify '%s._f0'",objname);
	  Py_DECREF(f0obj);
	  return 1;
	}
    }

    // The _epoch attribute is mandatory
    epoch_ptr = calloc(1,sizeof(LIGOTimeGPS));
    if (!epoch_ptr) {
      PyErr_Format(PyExc_RuntimeError,
		   "Could not create output epoch object for '%s._epoch'",objname);
      return 1;
    }
    epoch_ptr->gpsSeconds = (ts->epoch).gpsSeconds;
    epoch_ptr->gpsNanoSeconds = (ts->epoch).gpsNanoSeconds;
    epochobj = SWIG_NewPointerObj((void *) epoch_ptr,$descriptor(LIGOTimeGPS *),SWIG_POINTER_OWN);
    if (!epochobj) {
      PyErr_Format(PyExc_RuntimeError,
		   "Could not create output epoch object for '%s._epoch'",objname);
      free(epoch_ptr);
      return 1;
    }
    if (PyObject_SetAttrString(argument,"_epoch",epochobj) == -1) {
      PyErr_Format(PyExc_RuntimeError,
		   "Could not modify '%s._epoch'",objname);
      Py_DECREF(epochobj);
      return 1;
    }

    // The _delta_t attribute is mandatory
    delta_tobj = PyFloat_FromDouble(ts->deltaT);
    if (!delta_tobj) {
      PyErr_Format(PyExc_RuntimeError,
		   "Could not create output delta_t object for argument '%s._delta_t'",objname);
      return 1;
    }
    if (PyObject_SetAttrString(argument,"_delta_t",delta_tobj) == -1) {
      PyErr_Format(PyExc_RuntimeError,
		   "Could not modify '%s._delta_t'",objname);
      Py_DECREF(delta_tobj);
      return 1;
    }

    // The _name attribute is optional
    if (PyObject_HasAttrString(argument,"_name")){
      nameobj = PyString_FromStringAndSize(ts->name,LALNameLength);
      // If ts->name was NULL, then nameobj is uninitalized
      if (!nameobj) {
	PyErr_Format(PyExc_RuntimeError,
		     "Could not create output name object for argument '%s._name'"
		     objname);
	return 1;
      }
      if (PyDict_SetAttrString(argument,"_name",nameobj)) {
	PyErr_Format(PyExc_RuntimeError,
		     "Could not modify '%s._name'",objname);
	Py_DECREF(nameobj);
	return 1;
      }
    }

    // The _sample_units attribute is optional
    if (PyObject_HasAttrString(argument,"_sample_units"){
	sampleUnits_ptr = calloc(1,sizeof(LALUnit));
	if (!sampleUnits_ptr) {
	  PyErr_Format(PyExc_RuntimeError,
		       "Could not create output sample_units object for argument '%s._sample_units",
		       objname);
	  return 1;
	}
	sampleUnits_ptr->powerOfTen = (ts->sampleUnits).powerOfTen;
	for (i=0; i < LALNumUnits; i++) {
	  (sampleUnits_ptr->unitNumerator)[i] = (ts->sampleUnits).unitNumerator[i];
	  (sampleUnits_ptr->unitDenominatorMinusOne)[i] = (ts->sampleUnits).unitDenominatorMinusOne[i];
	}
	unitsobj = SWIG_NewPointerObj((void *) sampleUnits_ptr,$descriptor(LALUnit *),SWIG_POINTER_OWN);
	if (!unitsobj) {
	  PyErr_Format(PyExc_RuntimeError,
		       "Could not create output sample_units object for argument '%s._sample_units",
		       objname);
	  free(sampleUnits_ptr);
	  return 1;
	}
	if (PyObject_SetAttrString(argument,"_sample_units",unitsobj) == -1) {
	  PyErr_Format(PyExc_RuntimeError,
		       "Could not modify '%s._sample_units",objname);
	  Py_DECREF(unitsobj);
	  return 1;
	}
      }

      return 0;
      }
  }

%fragment("BuildArgoutTS","header",
	  fragment="BuildReturnFromValue",fragment="MarshallOutputTS") {};

/*

pycbc.types LAL typemaps


Below we have typemaps for each of the four floating-point LAL array-like types.
For each type there are four sets of typemaps:

(1) INPUT_<TYPE>{V,TS,FS}    *<TYPE>{Vector,TimeSeries,FrequencySeries}
(2) NEWOUT_<TYPE>{V,TS,FS}   *<TYPE>{Vector,TimeSeries,FrequencySeries}
(3) NONEOUT_<TYPE>{V,TS,FS}  *<TYPE>{Vector,TimeSeries,FrequencySeries}
(4) ARGOUT_<TYPE>{V,TS,FS}  **<TYPE>{Vector,TimeSeries,FrequencySeries}

where <TYPE> is one of REAL4, REAL8, COMPLEX8, or COMPLEX16.

The INPUT typemap should be applied to any argument of that array-like type to a LAL function,
and will cause the corresponding Python wrapped function to expect (directly) an instance of the
appropriate type from pycbc.types.  The _data property of this input argument should be a
C-contiguous, one-dimensional Numpy array of the dtype appropriate to that vector. Note that
this vector may in fact be treated by the XLAL function as "output", with its contents
modified in place. The elements of _data could have been modified, or also any of its properties
that can be set by the constructor.

The NEWOUT typemaps are for when a function returns a newly-allocated vector
of that type. This function will be wrapped into one which returns a newly allocated
instance of pycbc.types.{Array,TimeSeries,FrequencySeries}, with its '_data' element set to the
appropriate numpy type, and avoiding any memory copies. Other properties will be set as appropriate
to that specific array-like type (e.g. epoch, delta_t, etc).

The NONEOUT typemap is for functions that return a vector, but that vector is in
fact the same as one of the function's input vectors (which has been modified in
place).  In this case the wrapped function will always return "None" on successful
completion, and the effect of the function should be accessed through the
appropriate input input numpy array.

The ARGOUT typemap is for arguments that are double-pointers to an array-like type. These will
be wrapped into Python functions returning (possibly in a list, if there is more than one
return value) the new instances of the appropriate pycbc.type object created by those functions.
There will be no corresponding input argument to the wrapped function.


All of the typemaps except the NONEOUT typemaps have additional features which
will deallocate the temporary struct needed to pass the necessary memory between
Python and LAL.  These typemaps ("freearg" and "newfree") should not be modified
or disabled or memory leaks will result.

** IMPORTANT NOTE **

Not all XLAL functions will leave the location of their internal memory unchanged.
In particular any function that calls realloc() on a vector's data (including
functions that "cut" or "resize" vectors) can change the location of the data
pointer.  There is no way to accomodate this into Numpy's memory model, so you
should ensure that you never SWIG-wrap (with the typemaps of this file) any
function that may change the location in memory of the associated vector struct's
data. The best you might expect is a difficult-to-reproduce segfault.

YOU HAVE BEEN WARNED!

*/


// Typemaps for REAL4Vectors:

%typemap(in, fragment="MarshallInputVector") REAL4Vector *INPUT_REAL4V {
  $1 =(REAL4Vector *) MarshallInputVector($input,NPY_FLOAT32,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(freearg) REAL4Vector *INPUT_REAL4V {
  if ($1) {
    free((REAL4Vector *) $1);
  }
 }

%typemap(out, fragment="MarshallOutputVector") REAL4Vector *NEWOUT_REAL4V{
  $result = MarshallOutputVector((GenericVector *) $1,NPY_FLOAT32);
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) REAL4Vector *NEWOUT_REAL4V{
  free( (REAL4Vector *) $1);
 }

%typemap(out) REAL4Vector *NONEOUT_REAL4V{
  Py_INCREF(Py_None);
  $result = Py_None;
 }

%typemap(in,numinputs=0) REAL4Vector **ARGOUT_REAL4V (REAL4Vector *temp) {
  temp = NULL;
  $1 = &temp;
 }

%typemap(argout, fragment="BuildArgoutVector") REAL4Vector **ARGOUT_REAL4V {
  $result = BuildReturnFromValue($result,
				 MarshallOutputVector((GenericVector *) *($1),NPY_FLOAT32));
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) REAL4Vector **ARGOUT_REAL4V {
  free( (REAL4Vector *) *($1));
}


// Typemaps for REAL8Vectors:

%typemap(in, fragment="MarshallInputVector") REAL8Vector *INPUT_REAL8V {
  $1 =(REAL8Vector *) MarshallInputVector($input,NPY_FLOAT64,"$1_name");
  if (!($1)) SWIG_fail;
 }

%typemap(freearg) REAL8Vector *INPUT_REAL8V {
  if ($1) {
    free((REAL8Vector *) $1);
  }
 }

%typemap(out, fragment="MarshallOutputVector") REAL8Vector *NEWOUT_REAL8V{
  $result = MarshallOutputVector((GenericVector *) $1,NPY_FLOAT64);
  if (!($result)) SWIG_fail;
}

%typemap(newfree) REAL8Vector *NEWOUT_REAL8V{
  free( (REAL8Vector *) $1);
 }

%typemap(out) REAL8Vector *NONEOUT_REAL8V{
  Py_INCREF(Py_None);
  $result = Py_None;
}

%typemap(in,numinputs=0) REAL8Vector **ARGOUT_REAL8V (REAL8Vector *temp) {
  temp = NULL;
  $1 = &temp;
 }

%typemap(argout, fragment="BuildArgoutVector") REAL8Vector **ARGOUT_REAL8V {
  $result = BuildReturnFromValue($result,
				 MarshallOutputVector((GenericVector *) *($1),NPY_FLOAT64));
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) REAL8Vector **ARGOUT_REAL8V {
  free( (REAL8Vector *) *($1));
}

// Typemaps for COMPLEX8Vectors:

%typemap(in, fragment="MarshallInputVector") COMPLEX8Vector *INPUT_COMPLEX8V {
  $1 =(COMPLEX8Vector *) MarshallInputVector($input,NPY_COMPLEX64,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(freearg) COMPLEX8Vector *INPUT_COMPLEX8V {
  if ($1) {
    free((COMPLEX8Vector *) $1);
  }
}

%typemap(out, fragment="MarshallOutputVector") COMPLEX8Vector *NEWOUT_COMPLEX8V{
  $result = MarshallOutputVector((GenericVector *) $1,NPY_COMPLEX64);
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) COMPLEX8Vector *NEWOUT_COMPLEX8V{
  free( (COMPLEX8Vector *) $1);
 }

%typemap(out) COMPLEX8Vector *NONEOUT_COMPLEX8V{
  Py_INCREF(Py_None);
  $result = Py_None;
 }

%typemap(in,numinputs=0) COMPLEX8Vector **ARGOUT_COMPLEX8V (COMPLEX8Vector *temp) {
  temp = NULL;
  $1 = &temp;
 }

%typemap(argout, fragment="BuildArgoutVector") COMPLEX8Vector **ARGOUT_COMPLEX8V {
  $result = BuildReturnFromValue($result,
				 MarshallOutputVector((GenericVector *) *($1),NPY_COMPLEX64));
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) COMPLEX8Vector **ARGOUT_COMPLEX8V {
  free( (COMPLEX8Vector *) *($1));
}

// Typemaps for COMPLEX16Vectors:

%typemap(in, fragment="MarshallInputVector") COMPLEX16Vector *INPUT_COMPLEX16V {
  $1 =(COMPLEX8Vector *) MarshallInputVector($input,NPY_COMPLEX128,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(freearg) COMPLEX16Vector *INPUT_COMPLEX16V {
  if ($1) {
    free((COMPLEX16Vector *) $1);
  }
}

%typemap(out, fragment="MarshallOutputVector") COMPLEX16Vector *NEWOUT_COMPLEX16V{
  $result = MarshallOutputVector((GenericVector *) $1,NPY_COMPLEX128);
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) COMPLEX16Vector *NEWOUT_COMPLEX16V{
  free( (COMPLEX16Vector *) $1);
 }

%typemap(out) COMPLEX16Vector *NONEOUT_COMPLEX16V{
  Py_INCREF(Py_None);
  $result = Py_None;
 }

%typemap(in,numinputs=0) COMPLEX16Vector **ARGOUT_COMPLEX16V (COMPLEX16Vector *temp) {
  temp = NULL;
  $1 = &temp;
 }

%typemap(argout, fragment="BuildArgoutVector") COMPLEX16Vector **ARGOUT_COMPLEX8V {
  $result = BuildReturnFromValue($result,
				 MarshallOutputVector((GenericVector *) *($1),NPY_COMPLEX128));
  if (!($result)) SWIG_fail;
 }

%typemap(newfree) COMPLEX16Vector **ARGOUT_COMPLEX16V {
  free( (COMPLEX16Vector *) *($1));
}

// Typemaps for REAL4 Time Series

%typemap(in, fragment="MarshallInputTS") REAL4TimeSeries *INPUT_REAL4TS {
  $1 =(REAL4TimeSeries *) MarshallInputTS($input,NPY_FLOAT32,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(argout, fragment="MarshallArgoutTS") REAL4TimeSeries *INPUT_REAL4TS {
  if (MarshallArgoutTS($input,$1,"$1_name") ) SWIG_fail;
}

%typemap(freearg) REAL4TimeSeries *INPUT_REAL4TS {
  if ($1) {
    if ( ((REAL4TimeSeries *)$1)->data) {
      free ((REAL4Vector *) ((REAL4TimeSeries *)$1)->data);
    }
    free((REAL4TimeSeries *) $1);
  }
}

%typemap(out, fragment="MarshallOutputTS") REAL4TimeSeries *NEWOUT_REAL4TS{
  $result = MarshallOutputTS((GenericTS *) $1,NPY_FLOAT32);
  if (!($result)) SWIG_fail;
}

%typemap(newfree) REAL4TimeSeries *NEWOUT_REAL4TS{
  if ( ((REAL4TimeSeries *) $1)->data) free( (REAL4Vector *)((REAL4TimeSeries *) $1)->data);
  free( (REAL4TimeSeries *) $1);
}

%typemap(out) REAL4TimeSeries *NONEOUT_REAL4TS{
  Py_INCREF(Py_None);
  $result = Py_None;
}

%typemap(in,numinputs=0) REAL4TimeSeries **ARGOUT_REAL4TS (REAL4TimeSeries *temp) {
  temp = NULL;
  $1 = &temp;
}

%typemap(argout, fragment="BuildArgoutTS") REAL4TimeSeries **ARGOUT_REAL4TS {
  $result = BuildReturnFromValue($result,
				 MarshallOutputTS((GenericTS *) *($1),NPY_FLOAT32));
  if (!($result)) SWIG_fail;
}

// Typemaps for REAL8 Time Series

%typemap(in, fragment="MarshallInputTS") REAL8TimeSeries *INPUT_REAL8TS {
  $1 =(REAL8TimeSeries *) MarshallInputTS($input,NPY_FLOAT64,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(argout, fragment="MarshallArgoutTS") REAL8TimeSeries *INPUT_REAL8TS {
  if (MarshallArgoutTS($input,$1,"$1_name") ) SWIG_fail;
}

%typemap(freearg) REAL8TimeSeries *INPUT_REAL8TS {
  if ($1) {
    if ( ((REAL8TimeSeries *)$1)->data) {
      free ((REAL8Vector *) ((REAL8TimeSeries *)$1)->data);
    }
    free((REAL8TimeSeries *) $1);
  }
}

%typemap(out, fragment="MarshallOutputTS") REAL8TimeSeries *NEWOUT_REAL8TS{
  $result = MarshallOutputTS((GenericTS *) $1,NPY_FLOAT64);
  if (!($result)) SWIG_fail;
}

%typemap(newfree) REAL8TimeSeries *NEWOUT_REAL8TS{
  if ( ((REAL8TimeSeries *) $1)->data) free( (REAL8Vector *)((REAL8TimeSeries *) $1)->data);
  free( (REAL8TimeSeries *) $1);
}

%typemap(out) REAL8TimeSeries *NONEOUT_REAL8TS{
  Py_INCREF(Py_None);
  $result = Py_None;
}

%typemap(in,numinputs=0) REAL8TimeSeries **ARGOUT_REAL8TS (REAL8TimeSeries *temp) {
  temp = NULL;
  $1 = &temp;
}

%typemap(argout, fragment="BuildArgoutTS") REAL8TimeSeries **ARGOUT_REAL8TS {
  $result = BuildReturnFromValue($result,
				 MarshallOutputTS((GenericTS *) *($1),NPY_FLOAT64));
  if (!($result)) SWIG_fail;
}


// Typemaps for COMPLEX8 Time Series

%typemap(in, fragment="MarshallInputTS") COMPLEX8TimeSeries *INPUT_COMPLEX8TS {
  $1 =(COMPLEX8TimeSeries *) MarshallInputTS($input,NPY_COMPLEX64,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(argout, fragment="MarshallArgoutTS") COMPLEX8TimeSeries *INPUT_COMPLEX8TS {
  if (MarshallArgoutTS($input,$1,"$1_name") ) SWIG_fail;
}

%typemap(freearg) COMPLEX8TimeSeries *INPUT_COMPLEX8TS {
  if ($1) {
    if ( ((COMPLEX8TimeSeries *)$1)->data) {
      free ((COMPLEX8Vector *) ((COMPLEX8TimeSeries *)$1)->data);
    }
    free((COMPLEX8TimeSeries *) $1);
  }
}

%typemap(out, fragment="MarshallOutputTS") COMPLEX8TimeSeries *NEWOUT_COMPLEX8TS{
  $result = MarshallOutputTS((GenericTS *) $1,NPY_COMPLEX64);
  if (!($result)) SWIG_fail;
}

%typemap(newfree) COMPLEX8TimeSeries *NEWOUT_COMPLEX8TS{
  if ( ((COMPLEX8TimeSeries *) $1)->data) free( (COMPLEX8Vector *)((COMPLEX8TimeSeries *) $1)->data);
  free( (COMPLEX8TimeSeries *) $1);
}

%typemap(out) COMPLEX8TimeSeries *NONEOUT_COMPLEX8TS{
  Py_INCREF(Py_None);
  $result = Py_None;
}

%typemap(in,numinputs=0) COMPLEX8TimeSeries **ARGOUT_COMPLEX8TS (COMPLEX8TimeSeries *temp) {
  temp = NULL;
  $1 = &temp;
}

%typemap(argout, fragment="BuildArgoutTS") COMPLEX8TimeSeries **ARGOUT_COMPLEX8TS {
  $result = BuildReturnFromValue($result,
				 MarshallOutputTS((GenericTS *) *($1),NPY_COMPLEX64));
  if (!($result)) SWIG_fail;
}

// Typemaps for COMPLEX16 Time Series

%typemap(in, fragment="MarshallInputTS") COMPLEX16TimeSeries *INPUT_COMPLEX16TS {
  $1 =(COMPLEX16TimeSeries *) MarshallInputTS($input,NPY_COMPLEX128,"$1_name");
  if (!($1)) SWIG_fail;
}

%typemap(argout, fragment="MarshallArgoutTS") COMPLEX16TimeSeries *INPUT_COMPLEX16TS {
  if (MarshallArgoutTS($input,$1,"$1_name") ) SWIG_fail;
}

%typemap(freearg) COMPLEX16TimeSeries *INPUT_COMPLEX16TS {
  if ($1) {
    if ( ((COMPLEX16TimeSeries *)$1)->data) {
      free ((COMPLEX16Vector *) ((COMPLEX16TimeSeries *)$1)->data);
    }
    free((COMPLEX16TimeSeries *) $1);
  }
}

%typemap(out, fragment="MarshallOutputTS") COMPLEX16TimeSeries *NEWOUT_COMPLEX16TS{
  $result = MarshallOutputTS((GenericTS *) $1,NPY_COMPLEX128);
  if (!($result)) SWIG_fail;
}

%typemap(newfree) COMPLEX16TimeSeries *NEWOUT_COMPLEX16TS{
  if ( ((COMPLEX16TimeSeries *) $1)->data) free( (COMPLEX16Vector *)((COMPLEX16TimeSeries *) $1)->data);
  free( (COMPLEX16TimeSeries *) $1);
}

%typemap(out) COMPLEX16TimeSeries *NONEOUT_COMPLEX16TS{
  Py_INCREF(Py_None);
  $result = Py_None;
}

%typemap(in,numinputs=0) COMPLEX16TimeSeries **ARGOUT_COMPLEX16TS (COMPLEX16TimeSeries *temp) {
  temp = NULL;
  $1 = &temp;
}

%typemap(argout, fragment="BuildArgoutTS") COMPLEX16TimeSeries **ARGOUT_COMPLEX16TS {
  $result = BuildReturnFromValue($result,
				 MarshallOutputTS((GenericTS *) *($1),NPY_COMPLEX128));
  if (!($result)) SWIG_fail;
}

// Some tests:
%rename("%s") XLALSSVectorMultiply;
%apply REAL4Vector *NONEOUT_REAL4V { REAL4Vector *XLALSSVectorMultiply };
%apply REAL4Vector *INPUT_REAL4V {REAL4Vector *};
extern REAL4Vector *XLALSSVectorMultiply(REAL4Vector *out, REAL4Vector *in1, REAL4Vector *in2);

%rename("%s") XLALCreateREAL4Vector;
%apply REAL4Vector *NEWOUT_REAL4V {REAL4Vector *XLALCreateREAL4Vector};
extern REAL4Vector *XLALCreateREAL4Vector(UINT4 length);


%rename("%s") XLALCOMPLEX8VectorFFT;
%apply COMPLEX8Vector *INPUT_COMPLEX8V {COMPLEX8Vector *};
extern int XLALCOMPLEX8VectorFFT(COMPLEX8Vector *output, COMPLEX8Vector *input, const COMPLEX8FFTPlan *plan );

