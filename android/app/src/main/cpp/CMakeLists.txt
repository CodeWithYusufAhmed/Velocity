cmake_minimum_required(VERSION 3.22)
project(velocity_rnnoise C CXX)

# RNNoise (xiph.org, BSD-3) + a small JNI bridge.
add_library(velocity_rnnoise SHARED
    rnnoise/src/denoise.c
    rnnoise/src/rnn.c
    rnnoise/src/rnn_data.c
    rnnoise/src/pitch.c
    rnnoise/src/celt_lpc.c
    rnnoise/src/kiss_fft.c
    rnnoise_jni.cpp)

target_include_directories(velocity_rnnoise PRIVATE rnnoise/include rnnoise/src)
target_compile_options(velocity_rnnoise PRIVATE -O3 -ffast-math)
target_compile_definitions(velocity_rnnoise PRIVATE FLOAT_APPROX)
target_link_libraries(velocity_rnnoise log)
