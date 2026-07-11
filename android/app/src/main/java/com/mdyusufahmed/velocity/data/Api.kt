package com.mdyusufahmed.velocity.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT

@Serializable data class RegisterRequest(
    val email: String, @SerialName("display_name") val displayName: String, val password: String)
@Serializable data class LoginRequest(val email: String, val password: String)
@Serializable data class GoogleLoginRequest(@SerialName("id_token") val idToken: String)
@Serializable data class RefreshRequest(@SerialName("refresh_token") val refreshToken: String)

@Serializable data class TokenPair(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String)
@Serializable data class UserOut(
    val id: Long, val email: String,
    @SerialName("display_name") val displayName: String, val balance: Long)
@Serializable data class AuthResponse(val user: UserOut, val tokens: TokenPair)

@Serializable data class OddsSlotDto(
    val position: Int, val name: String, val multiplier: Int,
    val probability: Double, val rtp: Double)

@Serializable data class MoneyNotSpent(
    @SerialName("free_coins_received") val freeCoinsReceived: Long,
    @SerialName("dollars_not_spent") val dollarsNotSpent: Double,
    @SerialName("estimate_note") val estimateNote: String)
@Serializable data class TodayStats(
    @SerialName("rounds_played") val roundsPlayed: Int,
    @SerialName("total_bet") val totalBet: Long,
    @SerialName("total_won") val totalWon: Long,
    @SerialName("biggest_win") val biggestWin: Long,
    @SerialName("bonus_claimed") val bonusClaimed: Boolean,
    @SerialName("rescues_used") val rescuesUsed: Int)
@Serializable data class Profile(
    val id: Long, val email: String,
    @SerialName("display_name") val displayName: String, val balance: Long,
    @SerialName("vip_tier") val vipTier: Int,
    @SerialName("money_not_spent") val moneyNotSpent: MoneyNotSpent,
    val today: TodayStats,
    @SerialName("daily_round_limit") val dailyRoundLimit: Int? = null)

@Serializable data class RoundLimitRequest(val limit: Int? = null)
@Serializable data class RoundLimitResponse(
    @SerialName("daily_round_limit") val dailyRoundLimit: Int? = null,
    @SerialName("pending_round_limit") val pendingRoundLimit: Int? = null,
    @SerialName("pending_effective_date") val pendingEffectiveDate: String? = null)

@Serializable data class Top3Entry(
    @SerialName("user_id") val userId: Long,
    @SerialName("display_name") val displayName: String, val won: Long)
@Serializable data class RecentRound(
    @SerialName("round_id") val roundId: Long,
    @SerialName("winning_position") val winningPosition: Int,
    val name: String, val multiplier: Int, val top3: List<Top3Entry> = emptyList())
@Serializable data class BalanceResponse(val balance: Long, val granted: Boolean)

interface VelocityApi {
    @POST("auth/register") suspend fun register(@Body body: RegisterRequest): AuthResponse
    @POST("auth/login") suspend fun login(@Body body: LoginRequest): AuthResponse
    @POST("auth/google") suspend fun google(@Body body: GoogleLoginRequest): AuthResponse
    @POST("auth/refresh") suspend fun refresh(@Body body: RefreshRequest): TokenPair
    @POST("auth/logout") suspend fun logout(@Body body: RefreshRequest)
    @GET("rounds/odds") suspend fun odds(): List<OddsSlotDto>
    @GET("me") suspend fun profile(): Profile
    @PUT("me/round-limit") suspend fun setRoundLimit(@Body body: RoundLimitRequest): RoundLimitResponse
    @GET("rounds/recent") suspend fun recentRounds(): List<RecentRound>
    @POST("me/bonus") suspend fun claimBonus(): BalanceResponse
    @POST("me/rescue") suspend fun claimRescue(): BalanceResponse
}
