package com.mdyusufahmed.velocity.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Casino
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.mdyusufahmed.velocity.R
import com.mdyusufahmed.velocity.ui.about.AboutScreen
import com.mdyusufahmed.velocity.ui.profile.ProfileScreen
import com.mdyusufahmed.velocity.ui.game.GameScreen
import com.mdyusufahmed.velocity.ui.friends.DmScreen
import com.mdyusufahmed.velocity.ui.friends.FriendsScreen
import com.mdyusufahmed.velocity.ui.tables.TableRoomScreen
import com.mdyusufahmed.velocity.ui.tables.TablesScreen
import com.mdyusufahmed.velocity.ui.settings.SettingsScreen

enum class Tab(val route: String, @StringRes val label: Int, val icon: ImageVector) {
    Tables("tables", R.string.tab_tables, Icons.Filled.RecordVoiceOver),  // first: social home
    Game("game", R.string.tab_game, Icons.Filled.Casino),
    Friends("friends", R.string.tab_friends, Icons.Filled.Group),
    Profile("profile", R.string.tab_profile, Icons.Filled.Person),
}

@Composable
fun VelocityApp() {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = backStackEntry?.destination
    val onTab = Tab.entries.any { t ->
        currentDestination?.hierarchy?.any { it.route == t.route } == true
    }

    Scaffold(
        bottomBar = {
            if (onTab) NavigationBar {
                Tab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = currentDestination?.hierarchy?.any { it.route == tab.route } == true,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.startDestinationId) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = null) },
                        label = { Text(stringResource(tab.label)) },
                    )
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Tab.Tables.route,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Tab.Game.route) { GameScreen() }
            composable(Tab.Tables.route) {
                TablesScreen(onOpenTable = { id, name ->
                    navController.navigate("table/$id/${java.net.URLEncoder.encode(name, "UTF-8")}")
                })
            }
            composable("table/{id}/{name}") { entry ->
                val id = entry.arguments?.getString("id")?.toLongOrNull() ?: return@composable
                val name = java.net.URLDecoder.decode(
                    entry.arguments?.getString("name") ?: "Table", "UTF-8")
                TableRoomScreen(tableId = id, tableName = name,
                    onExit = { navController.popBackStack() },
                    onOpenDm = { uid, uname ->
                        navController.navigate("dm/$uid/${java.net.URLEncoder.encode(uname, "UTF-8")}")
                    })
            }
            composable(Tab.Friends.route) {
                FriendsScreen(onOpenDm = { id, name ->
                    navController.navigate("dm/$id/${java.net.URLEncoder.encode(name, "UTF-8")}")
                })
            }
            composable("dm/{peerId}/{peerName}") {
                DmScreen(onBack = { navController.popBackStack() })
            }
            composable(Tab.Profile.route) {
                ProfileScreen(
                    onOpenSettings = { navController.navigate("settings") },
                    onOpenAbout = { navController.navigate("about") },
                    onOpenModerator = { navController.navigate("moderator") },
                )
            }
            composable("settings") { SettingsScreen() }
            composable("about") { AboutScreen() }
            composable("moderator") {
                com.mdyusufahmed.velocity.ui.mod.ModeratorScreen(
                    onBack = { navController.popBackStack() })
            }
        }
    }
}
