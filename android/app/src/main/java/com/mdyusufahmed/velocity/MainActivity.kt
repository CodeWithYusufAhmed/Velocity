package com.mdyusufahmed.velocity

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import com.mdyusufahmed.velocity.data.AuthRepository
import com.mdyusufahmed.velocity.data.ws.SocketManager
import com.mdyusufahmed.velocity.ui.VelocityApp
import com.mdyusufahmed.velocity.ui.auth.AuthScreen
import com.mdyusufahmed.velocity.ui.theme.VelocityTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var auth: AuthRepository
    @Inject lateinit var sockets: SocketManager
    @Inject lateinit var dms: com.mdyusufahmed.velocity.data.DmRepository  // eager: DM notifications

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        setContent {
            VelocityTheme {
                val loggedIn by auth.isLoggedIn.collectAsState(initial = null)
                LaunchedEffect(loggedIn) {
                    if (loggedIn == true) sockets.start() else if (loggedIn == false) sockets.stop()
                }
                when (loggedIn) {
                    true -> VelocityApp()
                    false -> AuthScreen()
                    null -> {} // brief flash while DataStore loads
                }
            }
        }
    }
}
