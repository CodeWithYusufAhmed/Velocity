package com.mdyusufahmed.velocity.ui.auth

import android.content.Context
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.mdyusufahmed.velocity.BuildConfig
import com.mdyusufahmed.velocity.data.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import retrofit2.HttpException
import javax.inject.Inject

data class AuthUiState(
    val loading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repo: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state
    val isLoggedIn = repo.isLoggedIn

    fun login(email: String, password: String) = run {
        repo.login(email.trim(), password)
    }

    fun register(email: String, name: String, password: String) = run {
        repo.register(email.trim(), name.trim(), password)
    }

    fun googleSignIn(activityContext: Context) = run {
        val option = GetGoogleIdOption.Builder()
            .setServerClientId(BuildConfig.GOOGLE_WEB_CLIENT_ID)
            .setFilterByAuthorizedAccounts(false)
            .build()
        val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
        val result = CredentialManager.create(activityContext)
            .getCredential(activityContext, request)
        val idToken = GoogleIdTokenCredential.createFrom(result.credential.data).idToken
        repo.googleLogin(idToken)
    }

    private fun run(block: suspend () -> Any) {
        viewModelScope.launch {
            _state.value = AuthUiState(loading = true)
            try {
                block()
                _state.value = AuthUiState()
            } catch (e: HttpException) {
                _state.value = AuthUiState(error = when (e.code()) {
                    401 -> "Invalid email or password"
                    409 -> "An account with this email already exists"
                    422 -> "Check your input (password must be 8+ characters)"
                    429 -> "Too many attempts — wait a minute and try again"
                    else -> "Server error (${e.code()})"
                })
            } catch (e: Exception) {
                _state.value = AuthUiState(
                    error = e.message?.takeIf { it.isNotBlank() } ?: "Could not connect")
            }
        }
    }
}
