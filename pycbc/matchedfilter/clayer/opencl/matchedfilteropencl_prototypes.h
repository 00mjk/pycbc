#ifndef MATCHEDFILTEROPENCL_PROTOTYPES_H
#define MATCHEDFILTEROPENCL_PROTOTYPES_H

#include <stdlib.h>


// prototypes of all methodes that will extend pure c typedefs
matched_filter_opencl_t* new_matched_filter_opencl_t();
void delete_matched_filter_opencl_t( matched_filter_opencl_t* );

//prototypes of all functions that swig wraps to methods
void gen_snr_opencl(cl_context_t* context,
                    real_vector_single_opencl_t* snr,
                    complex_vector_single_opencl_t* stilde, 
                    complex_vector_single_opencl_t* htilde);

#endif /* MATCHEDFILTEROPENCL_PROTOTYPES_H */
