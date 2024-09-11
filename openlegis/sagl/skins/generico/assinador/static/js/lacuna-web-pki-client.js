var pki = new LacunaWebPKI('AqYBZGVtby5vcGVubGVnaXMuY29tLmJyLGUtcHJvY2Vzc28ucmVjaWZlLnBlLmxlZy5icixlLXByb2Nlc3Nvcy5jYW1hcmF1YmVybGFuZGlhLm1nLmdvdi5icixsZWcuY2FtYXJhamFuZGlyYS5zcC5nb3YuYnIscHVibGljby5jYW1hcmFyaWJlaXJhb3ByZXRvLnNwLmdvdi5icixzYXBsLmFzc2lzLnNwLmxlZy5icixzYXBsLmhvcnRvbGFuZGlhLnNwLmxlZy5icixzYXBsLmliaXRpbmdhLnNwLmxlZy5icixzYXBsLmluZGFpYXR1YmEuc3AubGVnLmJyLHNhcGwuamFib3RpY2FiYWwuc3AubGVnLmJyLHNhcGwuanVuZGlhaS5zcC5sZWcuYnIsc2FwbC5tYXJpbGlhLnNwLmxlZy5icixzYXBsLnBpbmRhbW9uaGFuZ2FiYS5zcC5sZWcuYnIsc2lzdGVtYS5jYW1hcmFjYXJhZ3VhLnNwLmdvdi5icixzaXN0ZW1hLmNhbWFyYW1vZ2lndWFjdS5zcC5nb3YuYnJ0AGlwNDoxMC4wLjAuMC84LGlwNDoxMC4wLjAuMC84LGlwNDoxMjcuMC4wLjAvOCxpcDQ6MTI3LjAuMC4wLzgsaXA0OjE3Mi4xNi4wLjAvMTIsaXA0OjE3Mi4xNi4wLjAvMTIsaXA0OjE5Mi4xNjguMC4wLzE2CABTdGFuZGFyZAAAAAHEaMcErgu1Yvo2DIIr2L3bseHiKX0Cmp+IzOsRv7LTC9hDSa7OlF++em678ErupdeGgCQfWGR0LdTNtZcSChNEyIubiJ4OzpWXQjFStCcTQy1m/EvS0rmFQNid6rngSb0VnCa0GXnaV8MLToVY5nZej6XYZWgVM7KkiVmVWv14nuy3CgyQGX5zl0KMC6kfzPF3bg8Tt/XcagpbBRsRNJCq/RQBqmQvdtUZxaT55OUuvuj0WR9Lqfgon7oL8+T5yRP9ckB4upfbbJvcRw8JVpkyWuqqUGb9SX7yWx0Nbt9U97pusX9X88aUpp09rVfqb+tFF7nalArpce7tMjFT1tQh');

var token = $("#token").val();

function start() {
    log('Inicializando componente ...');
    pki.init({
        restPkiUrl: 'https://restpkiol.azurewebsites.net/',
        ready: onWebPkiReady,
        defaultFail: onWebPkiFail
    });
}

function onWebPkiReady() {
    log('Componente pronto, listando certificados.');
    pki.listCertificates().success(function (certs) {
        var select = $('#certificateSelect');
        for (var i = 0; i < certs.length; i++) {
            var cert = certs[i];
            select.append(
                $('<option />').val(cert.thumbprint).text(getCertText(cert))
            );
        }
    });
}

function getCertText(cert) {
    var text = cert.subjectName;
    if (new Date() > cert.validityEnd) {
        text = '[EXPIRED] ' + text;
    }
    return text;
}

function readCert() {
    var selectedCertThumb = $('#certificateSelect').val();
    log('Certificado disponível: ' + selectedCertThumb);
    pki.readCertificate(selectedCertThumb).success(function (certEncoding) {
        log('Resultado: ' + certEncoding);
    });
}

function log(message) {
    $('#logPanel').append('<p>' + message + '</p>');
    if (window.console) {
        window.console.log(message);
    }    
}

function sign() {
    $.blockUI({message: '<i class="mdi mdi-spin mdi-loading mdi-36px mt-2"></i> <h4>Assinando documento...</h4>'});
    var selectedCertThumbprint = $('#certificateSelect').val();
    pki.signWithRestPki({
        token: token,
        thumbprint: selectedCertThumbprint
    }).success(function() {
        $('#signForm').submit();
    });
}

function onWebPkiFail(ex) {
    alert(ex.userMessage + ' (' + ex.code + ')');
    console.log('Erro no WebPKI originado em ' + ex.origin + ': (' + ex.code + ') ' + ex.error);
}

$(function() {
    $('#signButton').click(sign);
    $('#refreshButton').click(readCert);
    start();
});

