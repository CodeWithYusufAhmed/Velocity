package com.mdyusufahmed.velocity.voice

import io.livekit.android.audio.AudioProcessorInterface
import java.nio.ByteBuffer
import java.nio.ByteOrder

object RNNoise {
    init { System.loadLibrary("velocity_rnnoise") }
    external fun create(): Long
    external fun destroy(state: Long)
    external fun process(state: Long, frame: FloatArray)
}

/**
 * "Studio Noise Removal" — RNNoise applied to the outgoing mic stream.
 *
 * WebRTC hands us 10 ms buffers split into frequency bands (floats,
 * numBands × numFrames). RNNoise wants 480-sample frames; we run one
 * denoiser state per band over 480-sample accumulations (adds ~20 ms of
 * latency, inaudible in a voice room). EXPERIMENTAL: off by default.
 */
class RNNoiseProcessor : AudioProcessorInterface {

    @Volatile var enabled: Boolean = false

    private class BandState {
        val state = RNNoise.create()
        val acc = FloatArray(480)      // input accumulator
        val out = FloatArray(480)      // denoised, being drained
        var accFill = 0
        var outAvail = 0
        var primed = false             // don't output until first frame done
    }

    private var bands: Array<BandState> = emptyArray()

    override fun isEnabled(): Boolean = enabled

    override fun getName(): String = "velocity-rnnoise"

    override fun initializeAudioProcessing(sampleRateHz: Int, numChannels: Int) {
        release()
    }

    override fun resetAudioProcessing(newRate: Int) {
        release()
    }

    override fun processAudio(numBands: Int, numFrames: Int, buffer: ByteBuffer) {
        if (!enabled) return
        if (bands.size != numBands) {
            release()
            bands = Array(numBands) { BandState() }
        }
        buffer.order(ByteOrder.nativeOrder())
        val fb = buffer.asFloatBuffer()
        val scratch = FloatArray(numFrames)
        for (b in 0 until numBands) {
            fb.position(b * numFrames)
            fb.get(scratch, 0, numFrames)
            val st = bands[b]
            for (i in 0 until numFrames) {
                st.acc[st.accFill++] = scratch[i]
                if (st.accFill == 480) {
                    RNNoise.process(st.state, st.acc)
                    st.acc.copyInto(st.out)
                    st.outAvail = 480
                    st.accFill = 0
                    st.primed = true
                }
                scratch[i] = if (st.primed && st.outAvail > 0)
                    st.out[480 - st.outAvail--] else scratch[i]
            }
            fb.position(b * numFrames)
            fb.put(scratch, 0, numFrames)
        }
    }

    fun release() {
        bands.forEach { RNNoise.destroy(it.state) }
        bands = emptyArray()
    }
}
