(() => {
  // Abrir os HTMLs por file:// usa o servidor de produção, publicado no domínio.
  // Use localhost somente quando a própria página estiver servida localmente.
  const isLocalPreview =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

  window.PROMOPULSE_API_BASE_URL = isLocalPreview
    ? "http://localhost:8000"
    : "https://jangustavo.me/apis/promopulse";
})();
