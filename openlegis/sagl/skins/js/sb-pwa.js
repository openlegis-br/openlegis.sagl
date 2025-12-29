document.addEventListener("DOMContentLoaded", async function(event) {
  // Verifica se o navegador suporta service workers
  if (!('serviceWorker' in navigator)) {
    return;
  }
  
  try {
    if (navigator.serviceWorker.controller) {
      // Service worker já está ativo, não precisa registrar novamente
      // Log apenas em modo de desenvolvimento (opcional)
      if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log('[SAGL] Service worker ativo');
      }
    } else {
      // Registra o service worker se ainda não estiver registrado
      let reg = await navigator.serviceWorker.register('sw.js', { scope: './'});
      console.log('[SAGL] Service worker registrado: ' + reg.scope);
    }
  } catch (error) {
    // Silenciosamente ignora erros de service worker (não crítico)
    console.warn('[SAGL] Erro ao registrar service worker:', error.message);
  }
});
