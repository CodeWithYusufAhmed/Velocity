package com.mdyusufahmed.velocity.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.DELETE
import retrofit2.http.Path
import retrofit2.http.Query

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
    @SerialName("daily_round_limit") val dailyRoundLimit: Int? = null,
    @SerialName("is_moderator") val isModerator: Boolean = false)

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

@Serializable data class TableDto(
    val id: Long, val name: String, val topic: String? = null,
    @SerialName("chair_count") val chairCount: Int,
    @SerialName("member_count") val memberCount: Int = 0, val speakers: Int = 0,
    @SerialName("owner_id") val ownerId: Long = 0)
@Serializable data class CreateTableRequest(
    val name: String, val topic: String? = null,
    @SerialName("chair_count") val chairCount: Int)
@Serializable data class JoinTableResponse(
    @SerialName("livekit_token") val livekitToken: String,
    @SerialName("livekit_url") val livekitUrl: String,
    val role: String, @SerialName("vip_tier") val vipTier: Int,
    @SerialName("chair_count") val chairCount: Int,
    val chairs: Map<String, Long> = emptyMap())
@Serializable data class MemberDto(
    val id: Long, @SerialName("display_name") val displayName: String,
    val role: String, @SerialName("vip_tier") val vipTier: Int,
    val chair: Int? = null, @SerialName("has_avatar") val hasAvatar: Boolean = false,
    val muted: Boolean = false)
@Serializable data class BlockedUserDto(
    @SerialName("user_id") val userId: Long,
    @SerialName("display_name") val displayName: String)
@Serializable data class GiftVipRequest(@SerialName("user_id") val userId: Long, val tier: Int)
@Serializable data class GiftCoinsRequest(@SerialName("user_id") val userId: Long, val amount: Long)
@Serializable data class BanRequest(@SerialName("user_id") val userId: Long, val minutes: Int? = null)
@Serializable data class ModVip(
    @SerialName("user_id") val userId: Long,
    @SerialName("display_name") val displayName: String,
    val tier: Int, @SerialName("expires_at") val expiresAt: String)
@Serializable data class ModReport(
    val id: Long, val reporter: String, val reported: String,
    @SerialName("reported_id") val reportedId: Long, val reason: String, val note: String? = null)
@Serializable data class TargetRequest(@SerialName("user_id") val userId: Long)
@Serializable data class SitRequest(val position: Int)
@Serializable data class ReportRequest(
    @SerialName("user_id") val userId: Long, val reason: String,
    val note: String? = null, @SerialName("table_id") val tableId: Long? = null)
@Serializable data class KickResponse(
    val kicked: Boolean = false, val reason: String? = null)

@Serializable data class FriendDto(
    val id: Long, @SerialName("display_name") val displayName: String,
    val online: Boolean = false, @SerialName("vip_tier") val vipTier: Int = 0)
@Serializable data class FriendsList(
    @SerialName("friend_limit") val friendLimit: Int, val count: Int,
    val friends: List<FriendDto>)
@Serializable data class FriendRequestDto(
    val id: Long, @SerialName("sender_id") val senderId: Long,
    @SerialName("recipient_id") val recipientId: Long,
    @SerialName("sender_name") val senderName: String,
    @SerialName("recipient_name") val recipientName: String,
    val incoming: Boolean)
@Serializable data class SearchResult(
    val id: Long, @SerialName("display_name") val displayName: String,
    @SerialName("vip_tier") val vipTier: Int = 0)

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

    @GET("tables") suspend fun tables(): List<TableDto>
    @POST("tables") suspend fun createTable(@Body body: CreateTableRequest): TableDto
    @POST("tables/{id}/join") suspend fun joinTable(@Path("id") id: Long): JoinTableResponse
    @POST("tables/{id}/leave") suspend fun leaveTable(@Path("id") id: Long)
    @GET("tables/{id}/members") suspend fun members(@Path("id") id: Long): List<MemberDto>
    @POST("tables/{id}/sit") suspend fun sit(@Path("id") id: Long, @Body body: SitRequest)
    @POST("tables/{id}/stand") suspend fun stand(@Path("id") id: Long)
    @POST("tables/{id}/kick") suspend fun kick(@Path("id") id: Long, @Body body: TargetRequest): KickResponse
    @POST("tables/{id}/mute") suspend fun muteUser(@Path("id") id: Long, @Body body: TargetRequest)
    @POST("tables/{id}/block") suspend fun blockFromTable(@Path("id") id: Long, @Body body: TargetRequest)
    @POST("tables/{id}/chat-ban") suspend fun chatBan(@Path("id") id: Long, @Body body: TargetRequest)
    @POST("tables/{id}/admins") suspend fun grantAdmin(@Path("id") id: Long, @Body body: TargetRequest)
    @POST("reports") suspend fun report(@Body body: ReportRequest)
    @POST("blocks/{id}") suspend fun blockUser(@Path("id") id: Long)

    @Multipart @POST("me/avatar")
    suspend fun uploadAvatar(@Part file: MultipartBody.Part)

    @GET("friends") suspend fun friends(): FriendsList
    @GET("friends/requests") suspend fun friendRequests(): List<FriendRequestDto>
    @POST("friends/requests") suspend fun sendFriendRequest(@Body body: TargetRequest): kotlinx.serialization.json.JsonObject
    @POST("friends/requests/{id}/accept") suspend fun acceptRequest(@Path("id") id: Long)
    @POST("friends/requests/{id}/decline") suspend fun declineRequest(@Path("id") id: Long)
    @DELETE("friends/requests/{id}") suspend fun cancelRequest(@Path("id") id: Long)
    @DELETE("friends/{id}") suspend fun unfriend(@Path("id") id: Long)
    @GET("friends/search") suspend fun searchUsers(@Query("q") q: String): List<SearchResult>
    @GET("rounds/{id}/verify") suspend fun verifyRound(@Path("id") id: Long): VerifyResponse

    @GET("tables/{id}/blocks") suspend fun tableBlocks(@Path("id") id: Long): List<BlockedUserDto>
    @DELETE("tables/{id}/blocks/{uid}") suspend fun tableUnblock(@Path("id") id: Long, @Path("uid") uid: Long)
    @DELETE("tables/{id}") suspend fun closeTable(@Path("id") id: Long)

    @POST("mod/gift-vip") suspend fun modGiftVip(@Body body: GiftVipRequest): kotlinx.serialization.json.JsonObject
    @POST("mod/gift-coins") suspend fun modGiftCoins(@Body body: GiftCoinsRequest): kotlinx.serialization.json.JsonObject
    @POST("mod/ban") suspend fun modBan(@Body body: BanRequest): kotlinx.serialization.json.JsonObject
    @POST("mod/unban/{uid}") suspend fun modUnban(@Path("uid") uid: Long): kotlinx.serialization.json.JsonObject
    @GET("mod/reports") suspend fun modReports(): List<ModReport>
    @GET("mod/vips") suspend fun modVips(): List<ModVip>
    @DELETE("mod/vips/{uid}") suspend fun modRemoveVip(@Path("uid") uid: Long)
    @POST("mod/reports/{id}/resolve") suspend fun modResolveReport(@Path("id") id: Long)
}

@Serializable data class VerifyResponse(
    @SerialName("round_id") val roundId: Long,
    val revealed: Boolean,
    val commit: String,
    @SerialName("server_seed") val serverSeed: String? = null,
    @SerialName("winning_position") val winningPosition: Int? = null,
    @SerialName("commit_valid") val commitValid: Boolean? = null,
    @SerialName("result_valid") val resultValid: Boolean? = null,
    @SerialName("how_to_verify") val howToVerify: String? = null)
