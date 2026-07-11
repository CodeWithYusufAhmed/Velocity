package com.mdyusufahmed.velocity.data.db

import android.content.Context
import androidx.room.*
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.flow.Flow
import javax.inject.Singleton

/** DM history lives ONLY on this device (spec B4). Reinstalling clears it. */
@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val peerId: Long,          // the other participant
    val peerName: String,
    val text: String,
    val mine: Boolean,
    val sentAt: Long,          // epoch millis
    val state: String,         // sending | delivered | queued (offline on server, ≤30d)
)

data class ConversationRow(val peerId: Long, val peerName: String,
                           val text: String, val sentAt: Long)

@Dao
interface MessageDao {
    @Insert suspend fun insert(m: MessageEntity): Long

    @Query("UPDATE messages SET state = :state WHERE id = :id")
    suspend fun setState(id: Long, state: String)

    @Query("SELECT * FROM messages WHERE peerId = :peerId ORDER BY sentAt")
    fun conversation(peerId: Long): Flow<List<MessageEntity>>

    @Query("""SELECT peerId, peerName, text, sentAt FROM messages m
              WHERE sentAt = (SELECT MAX(sentAt) FROM messages WHERE peerId = m.peerId)
              GROUP BY peerId ORDER BY sentAt DESC""")
    fun conversations(): Flow<List<ConversationRow>>
}

@Database(entities = [MessageEntity::class], version = 1, exportSchema = false)
abstract class VelocityDb : RoomDatabase() {
    abstract fun messages(): MessageDao
}

@Module
@InstallIn(SingletonComponent::class)
object DbModule {
    @Provides @Singleton
    fun db(@ApplicationContext ctx: Context): VelocityDb =
        Room.databaseBuilder(ctx, VelocityDb::class.java, "velocity.db").build()

    @Provides fun messageDao(db: VelocityDb): MessageDao = db.messages()
}
