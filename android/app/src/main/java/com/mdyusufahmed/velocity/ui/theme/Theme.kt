package com.mdyusufahmed.velocity.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Velocity branding: dark asphalt, neon electric blue, amber. No casino imagery.
val Asphalt = Color(0xFF0D1117)
val AsphaltSurface = Color(0xFF161B22)
val NeonBlue = Color(0xFF2F81F7)
val Amber = Color(0xFFF0B429)
val TextPrimary = Color(0xFFE6EDF3)

private val VelocityColors = darkColorScheme(
    primary = NeonBlue,
    onPrimary = Color.White,
    secondary = Amber,
    onSecondary = Asphalt,
    background = Asphalt,
    onBackground = TextPrimary,
    surface = AsphaltSurface,
    onSurface = TextPrimary,
)

@Composable
fun VelocityTheme(content: @Composable () -> Unit) {
    // Always dark: the game is designed around the asphalt-and-neon look.
    MaterialTheme(colorScheme = VelocityColors, content = content)
}
