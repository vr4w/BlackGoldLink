// A fresh document ends the native POST redirect chain before Discogs login.
// Keep a normal link available when scripts or automatic navigation are blocked.
const discogsAuthorization = document.querySelector('[data-discogs-authorize]');
if (discogsAuthorization) {
  window.location.replace(discogsAuthorization.href);
}
