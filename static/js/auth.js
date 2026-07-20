

let activeEmail = "";

document.addEventListener('DOMContentLoaded', () => {
    setupOtpNavigation();
});


function goToStep(step) {
    const stepEmail = document.getElementById('stepEmail');
    const stepOtp = document.getElementById('stepOtp');
    const alertBox = document.getElementById('authAlert');
    
    
    alertBox.style.display = 'none';

    if (step === 'email') {
        stepOtp.classList.remove('active');
        setTimeout(() => {
            stepOtp.style.display = 'none';
            stepEmail.style.display = 'flex';
            setTimeout(() => stepEmail.classList.add('active'), 20);
        }, 300);
    } else if (step === 'otp') {
        stepEmail.classList.remove('active');
        setTimeout(() => {
            stepEmail.style.display = 'none';
            stepOtp.style.display = 'flex';
            setTimeout(() => stepOtp.classList.add('active'), 20);
            
            
            const firstBox = document.querySelector('.otp-box');
            if (firstBox) firstBox.focus();
        }, 300);
    }
}


function showAuthAlert(msg, type = 'error') {
    const alertBox = document.getElementById('authAlert');
    alertBox.textContent = msg;
    alertBox.className = `auth-alert ${type}`;
    alertBox.style.display = 'block';
    
    
    if (type === 'error') {
        alertBox.style.animation = 'none';
        alertBox.offsetHeight; 
        alertBox.style.animation = 'alertShake 0.4s ease';
    }
}


async function handleSendOtp(event) {
    if (event) event.preventDefault();
    
    const emailInput = document.getElementById('userEmail');
    let email = emailInput.value.trim();
    if (!email) return;

    if (!email.includes('@')) {
        email += '@gmail.com';
        emailInput.value = email;
    }

    activeEmail = email;
    const btn = document.getElementById('btnSendOtp');
    btn.disabled = true;
    btn.querySelector('span').textContent = "Sending code…";
    
    const alertBox = document.getElementById('authAlert');
    alertBox.style.display = 'none';

    try {
        const response = await fetch('/send-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            document.getElementById('displayTargetEmail').textContent = email;
            
            
            const boxes = document.querySelectorAll('.otp-box');
            boxes.forEach(box => {
                box.disabled = false;
                box.value = '';
            });
            const verifyBtn = document.getElementById('btnVerifyOtp');
            if (verifyBtn) {
                verifyBtn.disabled = false;
                verifyBtn.querySelector('span').textContent = "Verify and sign in";
            }


            goToStep('otp');
            showAuthAlert("Verification code sent to your email.", "success");
        } else {
            showAuthAlert(data.error || "Failed to send code. Please try again.");
        }
    } catch (err) {
        showAuthAlert("Connection error. Ensure your server is running.");
        console.error(err);
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = "Send verification code";
    }
}


async function resendOtp() {
    const resendBtn = document.getElementById('btnResendOtp');
    if (resendBtn) {
        resendBtn.disabled = true;
        resendBtn.textContent = "Sending…";
    }
    
    
    const boxes = document.querySelectorAll('.otp-box');
    boxes.forEach(box => box.value = '');

    try {
        const response = await fetch('/send-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: activeEmail })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            
            const boxes = document.querySelectorAll('.otp-box');
            boxes.forEach(box => {
                box.disabled = false;
                box.value = '';
            });
            const verifyBtn = document.getElementById('btnVerifyOtp');
            if (verifyBtn) {
                verifyBtn.disabled = false;
                verifyBtn.querySelector('span').textContent = "Verify and sign in";
            }


            showAuthAlert("A new verification code has been sent.", "success");
            
            
            const firstBox = document.querySelector('.otp-box');
            if (firstBox) firstBox.focus();
        } else {
            showAuthAlert(data.error || "Failed to resend code.");
        }
    } catch (err) {
        showAuthAlert("Connection error. Could not resend.");
    } finally {
        if (resendBtn) {
            resendBtn.disabled = false;
            resendBtn.textContent = "Resend code";
        }
    }
}


async function handleVerifyOtp(event) {
    if (event) event.preventDefault();
    
    const boxes = document.querySelectorAll('.otp-box');
    let otpCode = "";
    boxes.forEach(box => otpCode += box.value.trim());
    
    if (otpCode.length < 6) {
        showAuthAlert("Please enter all 6 digits of the code.");
        return;
    }

    const btn = document.getElementById('btnVerifyOtp');
    btn.disabled = true;
    btn.querySelector('span').textContent = "Verifying…";

    try {
        const response = await fetch('/verify-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: activeEmail, otp: otpCode })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAuthAlert("Authenticated successfully! Redirecting…", "success");
            setTimeout(() => {
                window.location.href = "/";
            }, 1000);
        } else {
            if (data.error === "TOO_MANY_ATTEMPTS") {
                showAuthAlert(data.message || "Too many failed attempts. This code is now invalid. Please request a new one.");
                
                btn.disabled = true;
                btn.querySelector('span').textContent = "Verification blocked";
                boxes.forEach(box => {
                    box.disabled = true;
                    box.value = '';
                });
            } else {
                showAuthAlert(data.error || "Incorrect or expired code. Please try again.");
                
                boxes.forEach((box, i) => {
                    box.value = '';
                    if (i === 0) box.focus();
                });
                btn.disabled = false;
                btn.querySelector('span').textContent = "Verify and sign in";
            }
        }
    } catch (err) {
        showAuthAlert("Connection error. Could not verify.");
        console.error(err);
        btn.disabled = false;
        btn.querySelector('span').textContent = "Verify and sign in";
    }
}


function setupOtpNavigation() {
    const boxes = document.querySelectorAll('.otp-box');
    
    boxes.forEach((box, index) => {
        
        box.addEventListener('input', (e) => {
            const val = box.value;
            
            if (!/^[0-9]$/.test(val)) {
                box.value = '';
                return;
            }
            
            if (val && index < boxes.length - 1) {
                boxes[index + 1].focus();
            }
            
            
            checkAndSubmitIfComplete();
        });
        
        
        box.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace') {
                if (!box.value && index > 0) {
                    boxes[index - 1].value = '';
                    boxes[index - 1].focus();
                } else {
                    box.value = '';
                }
            } else if (e.key === 'ArrowLeft' && index > 0) {
                boxes[index - 1].focus();
            } else if (e.key === 'ArrowRight' && index < boxes.length - 1) {
                boxes[index + 1].focus();
            }
        });
        
        
        box.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasteData = (e.clipboardData || window.clipboardData).getData('text').trim();
            if (/^\d{6}$/.test(pasteData)) {
                boxes.forEach((b, i) => {
                    b.value = pasteData[i];
                });
                boxes[boxes.length - 1].focus();
                checkAndSubmitIfComplete();
            }
        });
    });
}

function checkAndSubmitIfComplete() {
    const boxes = document.querySelectorAll('.otp-box');
    let isComplete = true;
    boxes.forEach(box => {
        if (!box.value) isComplete = false;
    });
    
    if (isComplete) {
        handleVerifyOtp();
    }
}




async function handleGoogleSignIn(response) {
    const idToken = response.credential;
    
    
    const alertBox = document.getElementById('authAlert');
    if (alertBox) alertBox.style.display = 'none';

    try {
        const res = await fetch('/api/auth/google', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_token: idToken })
        });
        
        const data = await res.json();
        
        if (res.ok && data.success) {
            showAuthAlert("Authenticated with Google! Redirecting...", "success");
            setTimeout(() => {
                window.location.href = "/";
            }, 1000);
        } else {
            showAuthAlert(data.error || "Google sign-in failed. Please try again.");
        }
    } catch (err) {
        showAuthAlert("Connection error during Google Sign-In.");
        console.error(err);
    }
}

