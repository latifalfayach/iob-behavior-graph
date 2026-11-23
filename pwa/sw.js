self.addEventListener("push", (e) => {
  let data = {};
  if (e.data) {
    try {
      data = e.data.json();
    } catch (_) {
      data = { body: e.data.text() };
    }
  }
  e.waitUntil(
    self.registration.showNotification(data.title || "☀️ Quick check-in", {
      body: data.body || "What are you up to? 🌅",
      icon: "icon-192.png",
      data: { url: data.url || "https://iob-behavior-graph-ehfisophxqtinrgvxsxryr.streamlit.app/" }
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const targetUrl =
    (e.notification.data && e.notification.data.url) ||
    "https://iob-behavior-graph-ehfisophxqtinrgvxsxryr.streamlit.app/";
  e.waitUntil(clients.openWindow(targetUrl));
});