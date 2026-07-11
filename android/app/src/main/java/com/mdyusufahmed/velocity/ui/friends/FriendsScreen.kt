package com.mdyusufahmed.velocity.ui.friends

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mdyusufahmed.velocity.data.*
import com.mdyusufahmed.velocity.data.db.ConversationRow
import com.mdyusufahmed.velocity.ui.tables.Avatar
import com.mdyusufahmed.velocity.ui.theme.Amber
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import retrofit2.HttpException
import javax.inject.Inject

@HiltViewModel
class FriendsViewModel @Inject constructor(
    private val api: VelocityApi,
    dms: DmRepository,
) : ViewModel() {
    val friends = MutableStateFlow<FriendsList?>(null)
    val requests = MutableStateFlow<List<FriendRequestDto>>(emptyList())
    val results = MutableStateFlow<List<SearchResult>>(emptyList())
    val notice = MutableStateFlow<String?>(null)
    val conversations = dms.conversations.stateIn(
        viewModelScope, SharingStarted.Eagerly, emptyList<ConversationRow>())

    fun refresh() = viewModelScope.launch {
        runCatching { api.friends() }.onSuccess { friends.value = it }
        runCatching { api.friendRequests() }.onSuccess { requests.value = it }
    }

    fun search(q: String) = viewModelScope.launch {
        if (q.length < 2) { results.value = emptyList(); return@launch }
        runCatching { api.searchUsers(q) }.onSuccess { results.value = it }
    }

    private fun act(block: suspend () -> Unit) = viewModelScope.launch {
        try { block(); refresh() }
        catch (e: HttpException) {
            notice.value = if (e.code() == 409) "Friend limit reached — existing friends are kept"
                           else "Action failed"
        }
    }

    fun add(userId: Long) = act { api.sendFriendRequest(TargetRequest(userId)); notice.value = "Request sent" }
    fun accept(id: Long) = act { api.acceptRequest(id) }
    fun decline(id: Long) = act { api.declineRequest(id) }
    fun cancel(id: Long) = act { api.cancelRequest(id) }
    fun unfriend(id: Long) = act { api.unfriend(id) }
    fun dismissNotice() { notice.value = null }
}

@Composable
fun FriendsScreen(onOpenDm: (Long, String) -> Unit, vm: FriendsViewModel = hiltViewModel()) {
    val friends by vm.friends.collectAsState()
    val requests by vm.requests.collectAsState()
    val results by vm.results.collectAsState()
    val convos by vm.conversations.collectAsState()
    val notice by vm.notice.collectAsState()
    var tab by remember { mutableStateOf(0) }
    var query by remember { mutableStateOf("") }

    LaunchedEffect(Unit) { vm.refresh() }

    Column(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Friends", style = MaterialTheme.typography.headlineMedium)
        TabRow(selectedTabIndex = tab) {
            listOf("Friends", "Chats", "Requests", "Find").forEachIndexed { i, label ->
                Tab(selected = tab == i, onClick = { tab = i },
                    text = { Text(label + if (i == 2 && requests.any { it.incoming })
                        " (${requests.count { it.incoming }})" else "") })
            }
        }
        when (tab) {
            0 -> {
                friends?.let {
                    Text("${it.count} / ${it.friendLimit} friends",
                        style = MaterialTheme.typography.labelSmall)
                }
                LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(friends?.friends ?: emptyList()) { f ->
                        Row(Modifier.fillMaxWidth().clickable { onOpenDm(f.id, f.displayName) }
                            .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Avatar(f.id, f.displayName, 40)
                            Column(Modifier.weight(1f)) {
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(f.displayName, style = MaterialTheme.typography.titleSmall)
                                    if (f.vipTier > 0) Text("VIP${f.vipTier}", color = Amber,
                                        style = MaterialTheme.typography.labelSmall)
                                }
                                Text(if (f.online) "● online" else "○ offline",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (f.online) androidx.compose.ui.graphics.Color(0xFF3FB950)
                                            else MaterialTheme.colorScheme.outline)
                            }
                            TextButton(onClick = { vm.unfriend(f.id) }) { Text("Unfriend") }
                        }
                    }
                }
            }
            1 -> LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(convos) { c ->
                    Row(Modifier.fillMaxWidth().clickable { onOpenDm(c.peerId, c.peerName) }
                        .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Avatar(c.peerId, c.peerName, 40)
                        Column {
                            Text(c.peerName, style = MaterialTheme.typography.titleSmall)
                            Text(c.text, maxLines = 1, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            2 -> LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                items(requests) { r ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(if (r.incoming) r.senderName else "→ ${r.recipientName}",
                            Modifier.weight(1f))
                        if (r.incoming) {
                            Button(onClick = { vm.accept(r.id) }) { Text("Accept") }
                            TextButton(onClick = { vm.decline(r.id) }) { Text("Decline") }
                        } else TextButton(onClick = { vm.cancel(r.id) }) { Text("Cancel") }
                    }
                }
            }
            3 -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(query, { query = it; vm.search(it) },
                    label = { Text("Search by name") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(results) { u ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Avatar(u.id, u.displayName, 36)
                            Text(u.displayName + if (u.vipTier > 0) "  VIP${u.vipTier}" else "",
                                Modifier.weight(1f))
                            Button(onClick = { vm.add(u.id) }) { Text("Add") }
                        }
                    }
                }
            }
        }
    }
    notice?.let {
        LaunchedEffect(it) { kotlinx.coroutines.delay(2500); vm.dismissNotice() }
        Snackbar(Modifier.padding(8.dp)) { Text(it) }
    }
}
