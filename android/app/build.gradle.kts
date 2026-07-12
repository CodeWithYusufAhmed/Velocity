import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

// Release signing from android/keystore.properties (gitignored) or CI env vars.
val ksProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val ksFile: String? = ksProps.getProperty("storeFile") ?: System.getenv("KEYSTORE_FILE")

android {
    namespace = "com.mdyusufahmed.velocity"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.mdyusufahmed.velocity"
        minSdk = 26
        targetSdk = 36
        versionCode = 4
        versionName = "1.0.3"
        // Dev server. 10.0.2.2 = host machine from the Android emulator.
        // For a real phone on the same Wi-Fi, change to the PC's LAN IP.
        buildConfigField("String", "SERVER_BASE_URL", "\"http://10.0.2.2:8000\"")
        // Google OAuth WEB client id (safe to be public; used as serverClientId).
        buildConfigField(
            "String", "GOOGLE_WEB_CLIENT_ID",
            "\"297133702720-ovv2bjabijharat222s73able76omd2b.apps.googleusercontent.com\""
        )
    }

    if (ksFile != null) {
        signingConfigs {
            create("release") {
                storeFile = file(ksFile)
                storePassword = ksProps.getProperty("storePassword") ?: System.getenv("KEYSTORE_PASSWORD")
                keyAlias = ksProps.getProperty("keyAlias") ?: System.getenv("KEY_ALIAS")
                keyPassword = ksProps.getProperty("keyPassword") ?: System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (ksFile != null) signingConfig = signingConfigs.getByName("release")
            // Production server (HTTPS via Cloudflare Tunnel)
            buildConfigField("String", "SERVER_BASE_URL", "\"https://velocity.mdyusufahmed.com\"")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore)
    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)
    implementation(libs.androidx.credentials)
    implementation(libs.androidx.credentials.play)
    implementation(libs.googleid)
    implementation(libs.livekit.android)
    implementation(libs.coil.compose)
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
