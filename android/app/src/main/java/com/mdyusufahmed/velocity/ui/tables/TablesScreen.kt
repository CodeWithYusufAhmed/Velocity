package com.mdyusufahmed.velocity.ui.tables

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
import com.mdyusufahmed.velocity.data.CreateTableRequest
import com.mdyusufahmed.velocity.data.TableDto
import com.mdyusufahmed.velocity.data.VelocityApi
import com.mdyusufahmed.velocity.ui.theme.Amber
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class TablesViewModel @Inject constructor(private val api: VelocityApi) : ViewModel() {
    val tables = MutableStateFlow<List<TableDto>>(emptyList())
    val error = MutableStateFlow<String?>(null)

    init { refresh() }

    fun refresh() = viewModelScope.launch {
        runCatching { api.tables() }
            .onSuccess { tables.value = it; error.value = null }
            .onFailure { error.value = "Could not load tables" }
    }

    fun create(name: String, topic: String?, chairs: Int, onCreated: (Long) -> Unit) =
        viewModelScope.launch {
            runCatching { api.createTable(CreateTableRequest(name, topic, chairs)) }
                .onSuccess { onCreated(it.id); refresh() }
                .onFailure { error.value = "Could not create table" }
        }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TablesScreen(onOpenTable: (Long, String) -> Unit, vm: TablesViewModel = hiltViewModel()) {
    val tables by vm.tables.collectAsState()
    val error by vm.error.collectAsState()
    var showCreate by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { vm.refresh() }

    Scaffold(floatingActionButton = {
        ExtendedFloatingActionButton(onClick = { showCreate = true }) { Text("+ New Table") }
    }) { pad ->
        Column(Modifier.padding(pad).padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Tables", style = MaterialTheme.typography.headlineMedium)
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if (tables.isEmpty()) Text("No open tables — start one!",
                style = MaterialTheme.typography.bodyMedium)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(tables) { t ->
                    Card(onClick = { onOpenTable(t.id, t.name) }) {
                        Row(Modifier.fillMaxWidth().padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically) {
                            Column {
                                Text(t.name, style = MaterialTheme.typography.titleMedium)
                                Text((t.topic?.let { "$it · " } ?: "") + "${t.chairCount} chairs",
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            Text("● ${t.memberCount} in · ${t.speakers} on mic",
                                color = Amber, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
    }

    if (showCreate) {
        var name by remember { mutableStateOf("") }
        var topic by remember { mutableStateOf("") }
        var chairs by remember { mutableStateOf(8) }
        ModalBottomSheet(onDismissRequest = { showCreate = false }) {
            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("New Table", style = MaterialTheme.typography.titleLarge)
                OutlinedTextField(name, { name = it }, label = { Text("Name") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                OutlinedTextField(topic, { topic = it }, label = { Text("Topic (optional)") },
                    singleLine = true, modifier = Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(8, 10, 12).forEach { c ->
                        FilterChip(selected = chairs == c, onClick = { chairs = c },
                            label = { Text("$c chairs") })
                    }
                }
                Button(
                    onClick = {
                        val tableName = name
                        vm.create(tableName, topic.ifBlank { null }, chairs) { id ->
                            showCreate = false; onOpenTable(id, tableName)
                        }
                    },
                    enabled = name.trim().length >= 2,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Create") }
                Spacer(Modifier.height(12.dp))
            }
        }
    }
}
