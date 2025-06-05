var pki = new LacunaWebPKI('AqYBZGVtby5vcGVubGVnaXMuY29tLmJyLGUtcHJvY2Vzc28ucmVjaWZlLnBlLmxlZy5icixlLXByb2Nlc3Nvcy5jYW1hcmF1YmVybGFuZGlhLm1nLmdvdi5icixsZWcuY2FtYXJhamFuZGlyYS5zcC5nb3YuYnIscHVibGljby5jYW1hcmFyaWJlaXJhb3ByZXRvLnNwLmdvdi5icixzYXBsLmFzc2lzLnNwLmxlZy5icixzYXBsLmhvcnRvbGFuZGlhLnNwLmxlZy5icixzYXBsLmliaXRpbmdhLnNwLmxlZy5icixzYXBsLmluZGFpYXR1YmEuc3AubGVnLmJyLHNhcGwuamFib3RpY2FiYWwuc3AubGVnLmJyLHNhcGwuanVuZGlhaS5zcC5sZWcuYnIsc2FwbC5tYXJpbGlhLnNwLmxlZy5icixzYXBsLnBpbmRhbW9uaGFuZ2FiYS5zcC5sZWcuYnIsc2lzdGVtYS5jYW1hcmFjYXJhZ3VhLnNwLmdvdi5icixzaXN0ZW1hLmNhbWFyYW1vZ2lndWFjdS5zcC5nb3YuYnJ0AGlwNDoxMC4wLjAuMC84LGlwNDoxMC4wLjAuMC84LGlwNDoxMjcuMC4wLjAvOCxpcDQ6MTI3LjAuMC4wLzgsaXA0OjE3Mi4xNi4wLjAvMTIsaXA0OjE3Mi4xNi4wLjAvMTIsaXA0OjE5Mi4xNjguMC4wLzE2CABTdGFuZGFyZAAAAAHEaMcErgu1Yvo2DIIr2L3bseHiKX0Cmp+IzOsRv7LTC9hDSa7OlF++em678ErupdeGgCQfWGR0LdTNtZcSChNEyIubiJ4OzpWXQjFStCcTQy1m/EvS0rmFQNid6rngSb0VnCa0GXnaV8MLToVY5nZej6XYZWgVM7KkiVmVWv14nuy3CgyQGX5zl0KMC6kfzPF3bg8Tt/XcagpbBRsRNJCq/RQBqmQvdtUZxaT55OUuvuj0WR9Lqfgon7oL8+T5yRP9ckB4upfbbJvcRw8JVpkyWuqqUGb9SX7yWx0Nbt9U97pusX9X88aUpp09rVfqb+tFF7nalArpce7tMjFT1tQh');

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
