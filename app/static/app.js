
const $ = (id) => document.getElementById(id);

async function api(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });

  let body;
  try {
    body = await response.json();
  } catch {
    body = { message: "Unexpected server response." };
  }

  if (!response.ok) {
    const error = new Error(body.message || "Something went wrong.");
    error.body = body;
    error.status = response.status;
    throw error;
  }

  return body;
}

function showMessage(element, message, kind = "error") {
  if (!element) return;
  element.textContent = message;
  element.className = `message message--${kind}`;
  element.hidden = false;
}

function clearMessage(element) {
  if (element) {
    element.hidden = true;
    element.textContent = "";
  }
}

function busy(button, isBusy, label) {
  if (!button) return;

  button.disabled = isBusy;
  button.classList.toggle("is-loading", isBusy);

  const span = button.querySelector(".btn__label");
  if (span && label) span.textContent = label;
}

function digitsFrom(selector) {
  return [...document.querySelectorAll(selector)]
    .map((el) => el.value)
    .join("");
}

function wireDigits(selector) {
  const inputs = [...document.querySelectorAll(selector)];

  inputs.forEach((input, index) => {
    input.addEventListener("input", () => {
      input.value = input.value.replace(/[^0-9]/g, "").slice(-1);
      input.classList.toggle("is-filled", Boolean(input.value));

      if (input.value && inputs[index + 1]) {
        inputs[index + 1].focus();
      }
    });

    input.addEventListener("keydown", (event) => {
      if (
        event.key === "Backspace" &&
        !input.value &&
        inputs[index - 1]
      ) {
        inputs[index - 1].focus();
      }

      if (event.key === "ArrowLeft" && inputs[index - 1]) {
        inputs[index - 1].focus();
      }

      if (event.key === "ArrowRight" && inputs[index + 1]) {
        inputs[index + 1].focus();
      }
    });

    input.addEventListener("paste", (event) => {
      const pasted = (
        event.clipboardData || window.clipboardData
      )
        .getData("text")
        .replace(/\D/g, "")
        .slice(0, 6);

      if (pasted) {
        event.preventDefault();

        inputs.forEach((item, i) => {
          item.value = pasted[i] || "";
          item.classList.toggle("is-filled", Boolean(item.value));
        });

        inputs[Math.min(pasted.length, inputs.length - 1)]?.focus();
      }
    });
  });

  return () => digitsFrom(selector);
}

function startTimer({
  seconds,
  timeId,
  captionId,
  ringId,
  timerId,
  resendButton,
  resendText,
}) {
  let remaining = seconds;
  const total = Math.max(seconds, 1);
  const circumference = 163.36;

  const update = () => {
    const time = $(timeId);
    const caption = $(captionId);
    const ring = $(ringId);
    const timer = $(timerId);

    if (time) {
      const minutes = Math.ceil(Math.max(remaining, 0) / 60);
      time.textContent = remaining <= 0 ? "Expired" : `${minutes} min`;
    }
    if (caption && remaining > 0) {
      caption.textContent = "Code expires in";
    }

    if (ring) {
      ring.style.strokeDashoffset = String(
        circumference * (1 - Math.max(remaining, 0) / total)
      );
    }

    if (timer) {
      timer.classList.toggle("is-expired", remaining <= 0);
    }

    if (remaining <= 0 && caption) {
      caption.textContent = "Code expired";
    }

    if (resendButton) {
      const cooldownLeft = Math.max(
        0,
        (window.__resendUntil || 0) - Date.now()
      );
      const secondsLeft = Math.ceil(cooldownLeft / 1000);

      resendButton.disabled = secondsLeft > 0;
      resendButton.textContent =
        secondsLeft > 0
          ? `Resend code in ${secondsLeft}s`
          : resendText;
    }
  };

  update();

  const interval = window.setInterval(() => {
    if (remaining > 0) remaining -= 1;
    update();

    if (
      remaining <= 0 &&
      Date.now() >= (window.__resendUntil || 0)
    ) {
      window.clearInterval(interval);
    }
  }, 1000);

  return () => window.clearInterval(interval);
}

// LOGIN PAGE
(function loginPage() {
  if (!$("email-form")) return;

  let currentEmail = "";
  let stopTimer = null;

  const loginMessage = $("login-message");
  const otpMessage = $("otp-message");
  const emailForm = $("email-form");
  const otpForm = $("otp-form");
  const sendButton = $("send-login-otp");
  const verifyButton = $("verify-login-otp");
  const resendButton = $("resend-login-otp");
  const getDigits = wireDigits(".otp-digit");

  emailForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage(loginMessage);

    const email = $("email").value.trim().toLowerCase();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showMessage(loginMessage, "Enter a valid email address.");
      $("email").focus();
      return;
    }

    busy(sendButton, true, "Checking email…");

    try {
      const result = await api("/api/auth/login/send-otp", {
        email,
      });

      // An unregistered email must not reach the OTP screen.
      if (result.registered === false) {
        if (stopTimer) {
          stopTimer();
          stopTimer = null;
        }

        $("otp-step").hidden = true;
        $("login-step").hidden = false;

        showMessage(
          loginMessage,
          result.message ||
            "This email is not registered. Please register first."
        );

        return;
      }

      currentEmail = email;
      $("otp-email").textContent = email;
      $("otp-target-email").value = email;

      $("login-step").hidden = true;
      $("otp-step").hidden = false;

      showMessage(
        otpMessage,
        result.message || "An OTP has been sent.",
        "success"
      );

      window.__resendUntil =
        Date.now() + (result.resend_after || 60) * 1000;

      if (stopTimer) stopTimer();

      stopTimer = startTimer({
        seconds: result.expires_in || 300,
        timeId: "timer-time",
        captionId: "timer-caption",
        ringId: "timer-progress",
        timerId: "timer",
        resendButton,
        resendText: "Resend OTP",
      });

      $("otp-1").focus();
    } catch (error) {
      showMessage(loginMessage, error.message);
    } finally {
      busy(sendButton, false, "Send OTP");
    }
  });

  otpForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage(otpMessage);

    const otp = getDigits();

    if (!/^[0-9]{6}$/.test(otp)) {
      showMessage(otpMessage, "Enter all 6 digits of your OTP.");
      $("otp-1").focus();
      return;
    }

    busy(verifyButton, true, "Verifying…");

    try {
      const result = await api("/api/auth/login/verify-otp", {
        email: currentEmail,
        otp,
      });

      showMessage(otpMessage, result.message, "success");

      window.location.assign(result.redirect || "/dashboard");
    } catch (error) {
      showMessage(otpMessage, error.message);

      $("otp-boxes")?.classList.add("has-error");

      window.setTimeout(() => {
        $("otp-boxes")?.classList.remove("has-error");
      }, 400);

      if (
        error.body?.code === "otp_expired" ||
        error.body?.code === "too_many_attempts"
      ) {
        resendButton.disabled = false;
        resendButton.textContent = "Resend OTP";
      }

      $("otp-1").focus();
    } finally {
      busy(verifyButton, false, "Verify and sign in");
    }
  });

  resendButton.addEventListener("click", async () => {
    clearMessage(otpMessage);
    resendButton.disabled = true;

    try {
      const result = await api("/api/auth/login/send-otp", {
        email: currentEmail,
      });

      if (result.registered === false) {
        $("otp-step").hidden = true;
        $("login-step").hidden = false;

        showMessage(
          loginMessage,
          result.message || "Please register this email first."
        );

        return;
      }

      document.querySelectorAll(".otp-digit").forEach((el) => {
        el.value = "";
        el.classList.remove("is-filled");
      });

      showMessage(
        otpMessage,
        result.message || "A new OTP has been sent.",
        "success"
      );

      window.__resendUntil =
        Date.now() + (result.resend_after || 60) * 1000;

      if (stopTimer) stopTimer();

      stopTimer = startTimer({
        seconds: result.expires_in || 300,
        timeId: "timer-time",
        captionId: "timer-caption",
        ringId: "timer-progress",
        timerId: "timer",
        resendButton,
        resendText: "Resend OTP",
      });

      $("otp-1").focus();
    } catch (error) {
      showMessage(otpMessage, error.message);
      resendButton.disabled = false;
      resendButton.textContent = "Resend OTP";
    }
  });

  $("change-email").addEventListener("click", () => {
    if (stopTimer) {
      stopTimer();
      stopTimer = null;
    }

    $("otp-step").hidden = true;
    $("login-step").hidden = false;

    clearMessage(loginMessage);
    $("email").value = currentEmail;
    $("email").focus();
  });
})();

// REGISTRATION PAGE
(function registerPage() {
  if (!$("register-form")) return;

  const form = $("register-form");
  const message = $("register-message");
  const otpMessage = $("register-otp-message");
  const submit = $("register-submit");
  const verifyButton = $("verify-register-otp");
  const resendButton = $("resend-register-otp");

  let email = "";
  let stopTimer = null;

  const getDigits = wireDigits(".reg-otp-digit");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage(message);

    const name = $("name").value.trim();
    email = $("register-email").value.trim().toLowerCase();

    if (name.length < 2) {
      showMessage(message, "Your name must be at least 2 characters.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showMessage(message, "Enter a valid email address.");
      return;
    }

    busy(submit, true, "Preparing registration…");

    try {
      await api("/api/auth/register", { name, email });

      const result = await api("/api/auth/register/send-otp", {
        email,
      });

      $("register-otp-email").textContent = email;
      $("register-step").hidden = true;
      $("register-otp-step").hidden = false;

      showMessage(otpMessage, result.message, "success");

      window.__resendUntil =
        Date.now() + (result.resend_after || 60) * 1000;

      if (stopTimer) stopTimer();

      stopTimer = startTimer({
        seconds: result.expires_in || 300,
        timeId: "reg-timer-time",
        captionId: "reg-timer-caption",
        ringId: "reg-timer-progress",
        timerId: "reg-timer",
        resendButton,
        resendText: "Resend OTP",
      });

      $("reg-otp-1").focus();
    } catch (error) {
      showMessage(message, error.message);
    } finally {
      busy(submit, false, "Continue to verification");
    }
  });

  $("register-otp-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage(otpMessage);

    const otp = getDigits();

    if (!/^[0-9]{6}$/.test(otp)) {
      showMessage(otpMessage, "Enter all 6 digits of your OTP.");
      return;
    }

    busy(verifyButton, true, "Verifying…");

    try {
      const result = await api("/api/auth/register/verify-otp", {
        email,
        otp,
      });

      $("register-otp-step").hidden = true;
      $("register-done").hidden = false;

      showMessage(
        $("register-done").querySelector(".message"),
        result.message,
        "success"
      );
    } catch (error) {
      showMessage(otpMessage, error.message);
    } finally {
      busy(verifyButton, false, "Verify email");
    }
  });

  resendButton.addEventListener("click", async () => {
    resendButton.disabled = true;

    try {
      const result = await api("/api/auth/register/send-otp", {
        email,
      });

      document.querySelectorAll(".reg-otp-digit").forEach((el) => {
        el.value = "";
        el.classList.remove("is-filled");
      });

      showMessage(otpMessage, result.message, "success");

      window.__resendUntil =
        Date.now() + (result.resend_after || 60) * 1000;

      if (stopTimer) stopTimer();

      stopTimer = startTimer({
        seconds: result.expires_in || 300,
        timeId: "reg-timer-time",
        captionId: "reg-timer-caption",
        ringId: "reg-timer-progress",
        timerId: "reg-timer",
        resendButton,
        resendText: "Resend OTP",
      });

      $("reg-otp-1").focus();
    } catch (error) {
      showMessage(otpMessage, error.message);
      resendButton.disabled = false;
      resendButton.textContent = "Resend OTP";
    }
  });
})();

// DASHBOARD LOGOUT
(function dashboardPage() {
  const logoutButton = $("logout-btn");
  if (!logoutButton) return;

  logoutButton.addEventListener("click", async () => {
    busy(logoutButton, true, "Logging out…");

    try {
      const result = await api("/api/auth/logout", {});
      window.location.assign(result.redirect || "/");
    } catch (error) {
      showMessage($("logout-message"), error.message);
      busy(logoutButton, false, "Log out");
    }
  });
})();
