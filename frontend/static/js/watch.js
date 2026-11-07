(function () {
  "use strict";

  const page = document.getElementById("watch-page");
  const videoId = page ? page.dataset.videoId : null;
  const tokenInput = document.getElementById("watch-token");
  const authStatus = document.getElementById("watch-auth-status");
  const likeButton = document.getElementById("like-button");
  const likeCount = document.getElementById("like-count");
  const likeIcon = document.getElementById("like-icon");
  const commentForm = document.getElementById("comment-form");
  const commentContent = document.getElementById("comment-content");
  const commentStatus = document.getElementById("comment-status");

  if (!videoId) {
    return;
  }

  tokenInput.value = localStorage.getItem("access_token") || "";
  tokenInput.addEventListener("input", function () {
    localStorage.setItem("access_token", tokenInput.value.trim());
  });

  function token() {
    return tokenInput.value.trim();
  }

  function setLikeState(liked, count) {
    likeButton.dataset.liked = liked ? "true" : "false";
    likeCount.textContent = String(count);
    likeIcon.style.color = liked ? "#dc2626" : "";
  }

  function showAuthStatus(message, isError) {
    authStatus.textContent = message;
    authStatus.classList.toggle("text-red-700", Boolean(isError));
    authStatus.classList.toggle("text-amber-800", !isError);
  }

  async function refreshLikeState() {
    const headers = {};
    if (token()) {
      headers.Authorization = "Bearer " + token();
    }
    try {
      const response = await fetch("/videos/" + encodeURIComponent(videoId), { headers: headers });
      if (response.ok) {
        const data = await response.json();
        setLikeState(Boolean(data.liked), Number(data.like_count || 0));
      }
    } catch (_error) {
      // Feed/watch page still works offline; like state just stays as rendered.
    }
  }

  likeButton.addEventListener("click", async function () {
    if (!token()) {
      showAuthStatus("Вставьте access token, чтобы поставить лайк.", true);
      return;
    }
    const liked = likeButton.dataset.liked === "true";
    try {
      const response = await fetch("/videos/" + encodeURIComponent(videoId) + "/like", {
        method: liked ? "DELETE" : "POST",
        headers: { Authorization: "Bearer " + token() }
      });
      if (!response.ok) {
        throw new Error("Не удалось изменить лайк");
      }
      const data = await response.json();
      setLikeState(Boolean(data.liked), Number(data.like_count || 0));
      showAuthStatus(liked ? "Лайк убран." : "Лайк поставлен.", false);
    } catch (error) {
      showAuthStatus(error.message, true);
    }
  });

  commentForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const content = commentContent.value.trim();
    if (!token()) {
      commentStatus.textContent = "Вставьте access token, чтобы комментировать.";
      commentStatus.className = "text-sm text-red-600";
      return;
    }
    if (!content) {
      return;
    }
    commentStatus.textContent = "Отправляем…";
    commentStatus.className = "text-sm text-gray-500";
    try {
      const response = await fetch("/videos/" + encodeURIComponent(videoId) + "/comments", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ content: content })
      });
      if (!response.ok) {
        const body = await response.json().catch(function () { return {}; });
        throw new Error(typeof body.detail === "string" ? body.detail : "Не удалось отправить комментарий");
      }
      window.location.reload();
    } catch (error) {
      commentStatus.textContent = error.message;
      commentStatus.className = "text-sm text-red-600";
    }
  });


  const reportButton = document.getElementById("report-button");
  const reportReason = document.getElementById("report-reason");
  const reportStatus = document.getElementById("report-status");

  reportButton.addEventListener("click", async function () {
    if (!token()) {
      reportStatus.textContent = "Вставьте access token, чтобы отправить жалобу.";
      return;
    }
    reportStatus.textContent = "Отправляем жалобу…";
    try {
      const response = await fetch("/videos/" + encodeURIComponent(videoId) + "/report", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ reason: reportReason.value })
      });
      const body = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : "Не удалось отправить жалобу");
      }
      reportStatus.textContent = body.auto_hidden
        ? "Жалоба принята. Видео автоматически скрыто."
        : "Жалоба принята.";
    } catch (error) {
      reportStatus.textContent = error.message;
    }
  });

  refreshLikeState();
})();