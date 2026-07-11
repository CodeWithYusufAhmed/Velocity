package com.mdyusufahmed.velocity

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.mdyusufahmed.velocity.ui.VelocityApp
import com.mdyusufahmed.velocity.ui.theme.VelocityTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VelocityTheme {
                VelocityApp()
            }
        }
    }
}
