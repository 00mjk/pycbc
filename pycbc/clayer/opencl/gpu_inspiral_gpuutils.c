// Copyright (C) 2011 Gergely Deberczeni (Gergely.Debreczeni@rmki.kfki.hu)
//
// This program is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License as published by the
// Free Software Foundation; either version 2 of the License, or (at your
// option) any later version.
//
// This program is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
// Public License for more details.
//
// You should have received a copy of the GNU General Public License along
// with this program; if not, write to the Free Software Foundation, Inc.,
// 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


//
// =============================================================================
//
//                                   Preamble
//
// =============================================================================
//
// OpenCL uitilites for initialization of context and error checking
// Merged from the 'GPU_INSPIRAL' opencl matched filter implementation

#include <stdio.h>
#include <string.h>
#include <CL/opencl.h>
#include "pycbcopencl_types.h"

//
// Mapping the Opencl error codes to error strings
// (Generated from OpenCL docs, should have a better solution soon
//
extern "C" void gpuinsp_getErrMessage(char * errMessage, const cl_int err) {

 switch (err) {
   case CL_SUCCESS:
         strcpy(errMessage,"CL_SUCCESS");
         break;
   case CL_DEVICE_NOT_FOUND:
         strcpy(errMessage,"CL_DEVICE_NOT_FOUND");
         break;
   case CL_DEVICE_NOT_AVAILABLE:
         strcpy(errMessage,"CL_DEVICE_NOT_AVAILABLE");
         break;
   case CL_COMPILER_NOT_AVAILABLE:
         strcpy(errMessage,"CL_COMPILER_NOT_AVAILABLE");
         break;
   case CL_MEM_OBJECT_ALLOCATION_FAILURE:
         strcpy(errMessage,"CL_MEM_OBJECT_ALLOCATION_FAILURE");
         break;
   case CL_OUT_OF_RESOURCES:
         strcpy(errMessage,"CL_OUT_OF_RESOURCES");
         break;
   case CL_OUT_OF_HOST_MEMORY:
         strcpy(errMessage,"CL_OUT_OF_HOST_MEMORY");
         break;
   case CL_PROFILING_INFO_NOT_AVAILABLE:
         strcpy(errMessage,"CL_PROFILING_INFO_NOT_AVAILABLE");
         break;
   case CL_MEM_COPY_OVERLAP:
         strcpy(errMessage,"CL_MEM_COPY_OVERLAP");
         break;
   case CL_IMAGE_FORMAT_MISMATCH:
         strcpy(errMessage,"CL_IMAGE_FORMAT_MISMATCH");
         break;
   case CL_IMAGE_FORMAT_NOT_SUPPORTED:
         strcpy(errMessage,"CL_IMAGE_FORMAT_NOT_SUPPORTED");
         break;
   case CL_BUILD_PROGRAM_FAILURE:
         strcpy(errMessage,"CL_BUILD_PROGRAM_FAILURE");
         break;
   case CL_MAP_FAILURE:
         strcpy(errMessage,"CL_MAP_FAILURE");
         break;
/* These are opencl 1.1 features not yet defined
   case CL_MISALIGNED_SUB_BUFFER_OFFSET:
         strcpy(errMessage,"CL_MISALIGNED_SUB_BUFFER_OFFSET");
         break;
   case CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST:
         strcpy(errMessage,"CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST");
         break;
*/
   case CL_INVALID_VALUE:
         strcpy(errMessage,"CL_INVALID_VALUE");
         break;
   case CL_INVALID_DEVICE_TYPE:
         strcpy(errMessage,"CL_INVALID_DEVICE_TYPE");
         break;
   case CL_INVALID_PLATFORM:
         strcpy(errMessage,"CL_INVALID_PLATFORM");
         break;
   case CL_INVALID_DEVICE:
         strcpy(errMessage,"CL_INVALID_DEVICE");
         break;
   case CL_INVALID_CONTEXT:
         strcpy(errMessage,"CL_INVALID_CONTEXT");
         break;
   case CL_INVALID_QUEUE_PROPERTIES:
         strcpy(errMessage,"CL_INVALID_QUEUE_PROPERTIES");
         break;
   case CL_INVALID_COMMAND_QUEUE:
         strcpy(errMessage,"CL_INVALID_COMMAND_QUEUE");
         break;
   case CL_INVALID_HOST_PTR:
         strcpy(errMessage,"CL_INVALID_HOST_PTR");
         break;
   case CL_INVALID_MEM_OBJECT:
         strcpy(errMessage,"CL_INVALID_MEM_OBJECT");
         break;
   case CL_INVALID_IMAGE_FORMAT_DESCRIPTOR:
         strcpy(errMessage,"CL_INVALID_IMAGE_FORMAT_DESCRIPTOR");
         break;
   case CL_INVALID_IMAGE_SIZE:
         strcpy(errMessage,"CL_INVALID_IMAGE_SIZE");
         break;
   case CL_INVALID_SAMPLER:
         strcpy(errMessage,"CL_INVALID_SAMPLER");
         break;
   case CL_INVALID_BINARY:
         strcpy(errMessage,"CL_INVALID_BINARY");
         break;
   case CL_INVALID_BUILD_OPTIONS:
         strcpy(errMessage,"CL_INVALID_BUILD_OPTIONS");
         break;
   case CL_INVALID_PROGRAM:
         strcpy(errMessage,"CL_INVALID_PROGRAM");
         break;
   case CL_INVALID_PROGRAM_EXECUTABLE:
         strcpy(errMessage,"CL_INVALID_PROGRAM_EXECUTABLE");
         break;
   case CL_INVALID_KERNEL_NAME:
         strcpy(errMessage,"CL_INVALID_KERNEL_NAME");
         break;
   case CL_INVALID_KERNEL_DEFINITION:
         strcpy(errMessage,"CL_INVALID_KERNEL_DEFINITION");
         break;
   case CL_INVALID_KERNEL:
         strcpy(errMessage,"CL_INVALID_KERNEL");
         break;
   case CL_INVALID_ARG_INDEX:
         strcpy(errMessage,"CL_INVALID_ARG_INDEX");
         break;
   case CL_INVALID_ARG_VALUE:
         strcpy(errMessage,"CL_INVALID_ARG_VALUE");
         break;
   case CL_INVALID_ARG_SIZE:
         strcpy(errMessage,"CL_INVALID_ARG_SIZE");
         break;
   case CL_INVALID_KERNEL_ARGS:
         strcpy(errMessage,"CL_INVALID_KERNEL_ARGS");
         break;
   case CL_INVALID_WORK_DIMENSION:
         strcpy(errMessage,"CL_INVALID_WORK_DIMENSION");
         break;
   case CL_INVALID_WORK_GROUP_SIZE:
         strcpy(errMessage,"CL_INVALID_WORK_GROUP_SIZE");
         break;
   case CL_INVALID_WORK_ITEM_SIZE:
         strcpy(errMessage,"CL_INVALID_WORK_ITEM_SIZE");
         break;
   case CL_INVALID_GLOBAL_OFFSET:
         strcpy(errMessage,"CL_INVALID_GLOBAL_OFFSET");
         break;
   case CL_INVALID_EVENT_WAIT_LIST:
         strcpy(errMessage,"CL_INVALID_EVENT_WAIT_LIST");
         break;
   case CL_INVALID_EVENT:
         strcpy(errMessage,"CL_INVALID_EVENT");
         break;
   case CL_INVALID_OPERATION:
         strcpy(errMessage,"CL_INVALID_OPERATION");
         break;
   case CL_INVALID_GL_OBJECT:
         strcpy(errMessage,"CL_INVALID_GL_OBJECT");
         break;
   case CL_INVALID_BUFFER_SIZE:
         strcpy(errMessage,"CL_INVALID_BUFFER_SIZE");
         break;
   case CL_INVALID_MIP_LEVEL:
         strcpy(errMessage,"CL_INVALID_MIP_LEVEL");
         break;
   case CL_INVALID_GLOBAL_WORK_SIZE:
         strcpy(errMessage,"CL_INVALID_GLOBAL_WORK_SIZE");
         break;
   default :
         strcpy(errMessage,"Unknown error");
         break;
  }
}


//
// Error checking and mapping error string to error codes
//
extern "C" cl_int gpuinsp_checkError(cl_int err, const char* errstr)
{
    char errMessage[200];
    if (err != CL_SUCCESS)
    {
        gpuinsp_getErrMessage(errMessage, err);
        fprintf(stderr, "ERROR: %s (%d, %s).\n", errstr, err,errMessage);
    }
    return err;
}

//
// Freeing and releasing the varioub openCl objects
//
extern "C" cl_int gpuinsp_DestroyGPU(cl_context_t * c) {
  if (c->kernel_queue) clReleaseCommandQueue(c->kernel_queue);
  if (c->io_queue) clReleaseCommandQueue(c->io_queue);
  return 0;
}

//
// The creation of context layer, platform,device id assignment happens here
//
extern "C" cl_int gpuinsp_InitGPU(cl_context_t* c, unsigned device_id)
{
  int  err;
  cl_uint 		 numPlatforms         = 0;
  cl_platform_id         Platform;
  cl_platform_id*	 Platforms            = new cl_platform_id[10];
  cl_context_properties  cps[3]               = {CL_CONTEXT_PLATFORM, (cl_context_properties) Platform, 0};
  cl_context_properties* cprops;
  cl_uint                numDevices           = 0;
  cl_device_id*          Devices;
  cl_device_id           AvailableDevice      = NULL;
  char                   DeviceName[200];

  cl_mem                 testdata_gpu;
  float*                 testdata_cpu         = NULL;
//Getting the platforms
  err = clGetPlatformIDs(0, NULL, &numPlatforms);
  if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;

  if (0 < numPlatforms)
    {
        err = clGetPlatformIDs(numPlatforms, Platforms, NULL);
        if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;
        c->platform = Platforms[0];
    } else {return -1;}

//Getting the context layer
  cps[0] = CL_CONTEXT_PLATFORM;
  cps[1] = (cl_context_properties) c->platform;
  cps[2] = 0;
  cprops = (NULL == c->platform) ? NULL : cps;

  err = clGetDeviceIDs(c->platform, CL_DEVICE_TYPE_GPU, 0, NULL, &numDevices);
  if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;
  Devices = (cl_device_id*) malloc(sizeof(cl_device_id) * numDevices);
  err = clGetDeviceIDs(c->platform, CL_DEVICE_TYPE_GPU, numDevices, Devices, NULL);
  if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;

//Getting the first available device
  for (unsigned int i = 0; i < numDevices; ++i)
      {
        cl_bool available;
        err = clGetDeviceInfo(Devices[i], CL_DEVICE_AVAILABLE, sizeof(cl_bool), &available, NULL);
        if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;
        if (available)
            {
                AvailableDevice = Devices[i];
                err = clGetDeviceInfo(Devices[i], CL_DEVICE_NAME, sizeof(DeviceName), DeviceName, NULL);
               if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;
                c->device = AvailableDevice;
                break;
            }
            else
            {
                err = clGetDeviceInfo(Devices[i], CL_DEVICE_NAME, sizeof(DeviceName), DeviceName, NULL);
                if (err == CL_SUCCESS)
                    printf("Device %s available for compute.", DeviceName);
                else
                    printf("Device #%d not available for compute.", i);
            }
        if (AvailableDevice == NULL)
        {
          return(-1);
        }
      }
  c->context = (cl_context) clCreateContext(cprops, 1, &AvailableDevice, NULL, NULL, &err);

//Creating the kernel and command queues

  c->kernel_queue = clCreateCommandQueue(c->context, c->device, 0, &err);
  if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;
  c->io_queue     = clCreateCommandQueue(c->context, c->device, 0, &err);
  if (gpuinsp_checkError(err,"Determining number of platforms") !=0)  goto cleanup;

// Performing a test mem array allocation and transfer

   testdata_cpu = (float*) malloc(sizeof(float)*1024);
   testdata_gpu = clCreateBuffer(c->context, CL_MEM_READ_WRITE, sizeof(float)*1024, NULL, &err);
   if (gpuinsp_checkError(err,"Test allocation in GPU memory") !=0)  goto cleanup;
   err = clEnqueueWriteBuffer(c->io_queue, testdata_gpu, CL_TRUE, 0, 1024*sizeof(float), testdata_cpu, 0, NULL, NULL);
   if (gpuinsp_checkError(err,"Test writing to  GPU memory") !=0)  goto cleanup;

//This is the return point in case of successful creation of the context
  return(0);

// Emergency exit
cleanup:
  gpuinsp_DestroyGPU(c);
  if (testdata_cpu) free(testdata_cpu);
  if (testdata_gpu) clReleaseMemObject(testdata_gpu);
  return(err);
}
