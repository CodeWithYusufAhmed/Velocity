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
import com.mdyusufahmed.velocity.ui.screens.FriendsScreen
import com.mdyusufahmed.velocity.ui.screens.GameScreen
import com.mdyusufahmed.velocity.ui.screens.TablesScreen
import com.mdyusufahmed.velocity.ui.settings.SettingsScreen

enum class Tab(val route: String, @StringRes val label: Int, val icon: ImageVector) {
    Game("game", R.string.tab_game, Icons.Filled.Casino),
    Tables("tables", R.string.tab_tables, Icons.Filled.RecordVoiceOver),
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
            startDestination = Tab.Game.route,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Tab.Game.route) { GameScreen() }
            composable(Tab.Tables.route) { TablesScreen() }
            composable(Tab.Friends.route) { FriendsScreen() }
            composable(Tab.Profile.route) {
                ProfileScreen(
                    onOpenSettings = { navController.navigate("settings") },
                    onOpenAbout = { navController.navigate("about") },
                )
            }
            composable("settings") { SettingsScreen() }
            composable("about") { AboutScreen() }
        }
    }
}
