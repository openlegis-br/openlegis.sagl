var pki = new LacunaWebPKI('AskBZGVtby5vcGVubGVnaXMuY29tLmJyLGUtcHJvY2Vzc28ucmVjaWZlLnBlLmxlZy5icixlLXByb2Nlc3Nvcy5jYW1hcmF1YmVybGFuZGlhLm1nLmdvdi5icixsZWcuY2FtYXJhamFuZGlyYS5zcC5nb3YuYnIscHVibGljby5jYW1hcmFyaWJlaXJhb3ByZXRvLnNwLmdvdi5icixzYXBsLmFzc2lzLnNwLmxlZy5icixzYXBsLmhvcnRvbGFuZGlhLnNwLmxlZy5icixzYXBsLmliaXRpbmdhLnNwLmxlZy5icixzYXBsLmluZGFpYXR1YmEuc3AubGVnLmJyLHNhcGwuamFib3RpY2FiYWwuc3AubGVnLmJyLHNhcGwuanVuZGlhaS5zcC5sZWcuYnIsc2FwbC5tYXJpbGlhLnNwLmxlZy5icixzYXBsLnBpbmRhbW9uaGFuZ2FiYS5zcC5sZWcuYnIsc2lzdGVtYS5jYW1hcmFjYW1wb2xpbXBvLnNwLmdvdi5icixzaXN0ZW1hLmNhbWFyYWNhcmFndWEuc3AuZ292LmJyLHNpc3RlbWEuY2FtYXJhbW9naWd1YWN1LnNwLmdvdi5icnQAaXA0OjEwLjAuMC4wLzgsaXA0OjEwLjAuMC4wLzgsaXA0OjEyNy4wLjAuMC84LGlwNDoxMjcuMC4wLjAvOCxpcDQ6MTcyLjE2LjAuMC8xMixpcDQ6MTcyLjE2LjAuMC8xMixpcDQ6MTkyLjE2OC4wLjAvMTYIAFN0YW5kYXJkAAAAAZlX+r8Fq6yp6ylKZCQYP+xitPF6tMDipodTO6mvllETWb/aKLGG4iNa72p2i1h0tTTzkcxWbSZRD7gBLB2WDWslv0vyiIP2VZN/vUwHJ59wxDxAzqMkTp6a2ky642Fv8IZfNLAUZ/smuFJ2edZJ6JgZ6NsFWdN5z3tjhzvyWptPhhaAaEVc0X1+XSgEvnC02TJQRoIYOQMwzg44TorLiYj0nLGEywbB/L+RTGjrFT2Pdfbu3cAp9KSMb3YHYL1USm3GxXAs9HA4Sts0+QUfDYNeiT3I2/L0duQTx8HcgMK0uwo+wPFt+0HuNSZ6ymNvNbgQTS6jI35NSr96tUvdW/Q=');

function initWebPki() {
  log('Inicializando Web PKI...');
  pki.init({
    restPkiUrl: 'https://restpkiol.azurewebsites.net/',
    ready: loadCertificates,
    defaultFail: onWebPkiFail
  });
}

function loadCertificates() {
  log('Componente pronto, listando certificados...');
  pki.listCertificates().success(function (certs) {
    var $select = $('#certificateSelect');
    $select.empty();
    if (certs.length === 0) {
      alert('Nenhum certificado foi encontrado. Verifique o seu e-CPF.');
      return;
    }

    $.each(certs, function (i, cert) {
      const label = getCertText(cert);
      $select.append($('<option />').val(cert.thumbprint).text(label));
    });

  }).error(function (err) {
    log('Erro ao listar certificados');
    onWebPkiFail(err);
  });
}

function getCertText(cert) {
  var text = cert.subjectName;
  if (new Date() > cert.validityEnd) {
    text = '[VENCIDO] ' + text;
  }
  return text;
}

function signDocument() {
  $.blockUI({ message: '<h4>Assinando documento...</h4>' });

  const token = $('#token').val();
  const thumbprint = $('#certificateSelect').val();

  if (!token || token.trim() === '') {
    $.unblockUI();
    alert('Token de assinatura ausente. Recarregue a página ou tente novamente.');
    return;
  }

  if (!thumbprint) {
    $.unblockUI();
    alert('Selecione um certificado digital.');
    return;
  }

  log('Iniciando assinatura com REST PKI...');
  pki.signWithRestPki({
    token: token,
    thumbprint: thumbprint
  }).success(function () {
    log('Assinatura concluída. Submetendo formulário.');
    $('#signForm').submit();
  }).error(function (ex) {
    $.unblockUI();
    onWebPkiFail(ex);
  });
}

function refreshCertificateList() {
  log('Atualizando lista de certificados...');
  $('#certificateSelect').empty();
  loadCertificates();
}

function onWebPkiFail(ex) {
  const msg = ex.userMessage || 'Erro inesperado.';
  const code = ex.code || 'sem código';
  const origin = ex.origin || 'desconhecida';

  alert(msg + ' (' + code + ')');
  console.error('Erro no WebPKI: ', ex);
  log(`Erro: ${msg} (code: ${code}, origin: ${origin})`);
}

function log(msg) {
  $('#logPanel').append('<p>' + msg + '</p>');
  if (console) console.log('[WebPKI] ' + msg);
}

$(function () {
  $('#signButton').on('click', signDocument);
  $('#refreshButton').on('click', refreshCertificateList);
  initWebPki();
});
