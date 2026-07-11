package com.mdyusufahmed.velocity.di

import com.mdyusufahmed.velocity.BuildConfig
import com.mdyusufahmed.velocity.data.RefreshRequest
import com.mdyusufahmed.velocity.data.TokenStore
import com.mdyusufahmed.velocity.data.VelocityApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    /** Plain client for /auth endpoints (no bearer header, no refresh loop). */
    private fun baseClient(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private fun retrofit(client: OkHttpClient): Retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.SERVER_BASE_URL + "/")
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    /** Unauthenticated API — used by the token refresh path to avoid recursion. */
    private fun plainApi(): VelocityApi = retrofit(baseClient()).create(VelocityApi::class.java)

    @Provides
    @Singleton
    fun api(tokens: TokenStore): VelocityApi {
        val refreshApi = plainApi()
        val authed = baseClient().newBuilder()
            .addInterceptor { chain ->
                val access = tokens.accessBlocking()
                val req = if (access != null && chain.request().header("Authorization") == null)
                    chain.request().newBuilder().header("Authorization", "Bearer $access").build()
                else chain.request()
                chain.proceed(req)
            }
            .authenticator(object : Authenticator {
                // On 401: rotate the refresh token once, retry the request.
                override fun authenticate(route: Route?, response: Response): Request? {
                    if (response.priorResponse != null) return null // already retried
                    val refresh = tokens.refreshBlocking() ?: return null
                    val pair = try {
                        kotlinx.coroutines.runBlocking { refreshApi.refresh(RefreshRequest(refresh)) }
                    } catch (e: Exception) {
                        return null // refresh failed → caller sees 401 → logout flow
                    }
                    tokens.saveBlocking(pair.accessToken, pair.refreshToken)
                    return response.request.newBuilder()
                        .header("Authorization", "Bearer ${pair.accessToken}").build()
                }
            })
            .build()
        return retrofit(authed).create(VelocityApi::class.java)
    }
}
