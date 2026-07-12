// JNI bridge for RNNoise. One DenoiseState per stream; frames are 480 float
// samples (10 ms @ 48 kHz), RNNoise's native frame size.
#include <jni.h>
#include <cstring>

extern "C" {
#include "rnnoise.h"
}

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_mdyusufahmed_velocity_voice_RNNoise_create(JNIEnv *, jclass) {
    return reinterpret_cast<jlong>(rnnoise_create(nullptr));
}

JNIEXPORT void JNICALL
Java_com_mdyusufahmed_velocity_voice_RNNoise_destroy(JNIEnv *, jclass, jlong state) {
    if (state) rnnoise_destroy(reinterpret_cast<DenoiseState *>(state));
}

// In/out: exactly 480 floats in WEBRTC float range (approx -32768..32767 —
// rnnoise expects short-range floats, which matches WebRTC's band buffers).
JNIEXPORT void JNICALL
Java_com_mdyusufahmed_velocity_voice_RNNoise_process(JNIEnv *env, jclass, jlong state,
                                                     jfloatArray frame) {
    if (!state) return;
    jfloat buf[480];
    env->GetFloatArrayRegion(frame, 0, 480, buf);
    rnnoise_process_frame(reinterpret_cast<DenoiseState *>(state), buf, buf);
    env->SetFloatArrayRegion(frame, 0, 480, buf);
}

}
