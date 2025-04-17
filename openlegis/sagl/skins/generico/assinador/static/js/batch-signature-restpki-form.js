// ------------------------------------------------------------------------------------------------
// Este arquivo contém a lógica para chamar o componente Web PKI para assinar um lote de documentos
// selecionados de uma lista.
// ------------------------------------------------------------------------------------------------
var batchSignatureRestPkiForm = (function () {

	// A classe Javascript "Queue"
	(function () {
		window.Queue = function () {
			this.items = [];
			this.writerCount = 0;
			this.readerCount = 0;
		};
		window.Queue.prototype.add = function (e) {
			this.items.push(e);
		};
		window.Queue.prototype.addRange = function (array) {
			for (var i = 0; i < array.length; i++) {
				this.add(array[i]);
			}
		};
		var _process = function (inQueue, processor, outQueue, endCallback) {
			var obj = inQueue.items.shift();
			if (obj !== undefined) {
				processor(obj, function (result) {
					if (result != null && outQueue != null) {
						outQueue.add(result);
					}
					_process(inQueue, processor, outQueue, endCallback);
				});
			} else if (inQueue.writerCount > 0) {
				setTimeout(function () {
					_process(inQueue, processor, outQueue, endCallback);
				}, 200);
			} else {
				--inQueue.readerCount;
				if (outQueue != null) {
					--outQueue.writerCount;
				}
				if (inQueue.readerCount == 0 && endCallback) {
					endCallback();
				}
			}
		};
		window.Queue.prototype.process = function (processor, options) {
			var threads = options.threads || 1;
			this.readerCount = threads;
			if (options.output) {
				options.output.writerCount = threads;
			}
			for (var i = 0; i < threads; i++) {
				_process(this, processor, options.output, options.completed);
			}
		};
	})();

	// Variáveis globais auxiliares.
	var startQueue = null;
	var performQueue = null;
	var completeQueue = null;
	var formElements = {};
	var pki = null;

	// ---------------------------------------------------------------------------------------------
	// Função chamada quando a página é carregada.
	// ---------------------------------------------------------------------------------------------
	function init(fe) {

		// Recebe os elementos do formulário passados como argumentos.
		formElements = fe;
		pki = new LacunaWebPKI('AqYBZGVtby5vcGVubGVnaXMuY29tLmJyLGUtcHJvY2Vzc28ucmVjaWZlLnBlLmxlZy5icixlLXByb2Nlc3Nvcy5jYW1hcmF1YmVybGFuZGlhLm1nLmdvdi5icixsZWcuY2FtYXJhamFuZGlyYS5zcC5nb3YuYnIscHVibGljby5jYW1hcmFyaWJlaXJhb3ByZXRvLnNwLmdvdi5icixzYXBsLmFzc2lzLnNwLmxlZy5icixzYXBsLmhvcnRvbGFuZGlhLnNwLmxlZy5icixzYXBsLmliaXRpbmdhLnNwLmxlZy5icixzYXBsLmluZGFpYXR1YmEuc3AubGVnLmJyLHNhcGwuamFib3RpY2FiYWwuc3AubGVnLmJyLHNhcGwuanVuZGlhaS5zcC5sZWcuYnIsc2FwbC5tYXJpbGlhLnNwLmxlZy5icixzYXBsLnBpbmRhbW9uaGFuZ2FiYS5zcC5sZWcuYnIsc2lzdGVtYS5jYW1hcmFjYXJhZ3VhLnNwLmdvdi5icixzaXN0ZW1hLmNhbWFyYW1vZ2lndWFjdS5zcC5nb3YuYnJ0AGlwNDoxMC4wLjAuMC84LGlwNDoxMC4wLjAuMC84LGlwNDoxMjcuMC4wLjAvOCxpcDQ6MTI3LjAuMC4wLzgsaXA0OjE3Mi4xNi4wLjAvMTIsaXA0OjE3Mi4xNi4wLjAvMTIsaXA0OjE5Mi4xNjguMC4wLzE2CABTdGFuZGFyZAAAAAHEaMcErgu1Yvo2DIIr2L3bseHiKX0Cmp+IzOsRv7LTC9hDSa7OlF++em678ErupdeGgCQfWGR0LdTNtZcSChNEyIubiJ4OzpWXQjFStCcTQy1m/EvS0rmFQNid6rngSb0VnCa0GXnaV8MLToVY5nZej6XYZWgVM7KkiVmVWv14nuy3CgyQGX5zl0KMC6kfzPF3bg8Tt/XcagpbBRsRNJCq/RQBqmQvdtUZxaT55OUuvuj0WR9Lqfgon7oL8+T5yRP9ckB4upfbbJvcRw8JVpkyWuqqUGb9SX7yWx0Nbt9U97pusX9X88aUpp09rVfqb+tFF7nalArpce7tMjFT1tQh');

		// Vincula os cliques dos botões.
		formElements.refreshButton.click(refresh);
		formElements.processSelectedFilesButton.click(signBatch); // Alterado para usar a função de assinatura em lote

		// Monitora a mudança nos checkboxes da lista de arquivos para habilitar/desabilitar o botão.
		formElements.fileList.on('change', '.file-checkbox', function () {
			var checkedCount = formElements.fileList.find('.file-checkbox:checked').length;
			formElements.processSelectedFilesButton.prop('disabled', checkedCount === 0);
		});

		// Bloqueia a interface do usuário enquanto preparamos as coisas.
		$.blockUI({message: 'Inicializando ...'});

		// Chama o método init() no objeto LacunaWebPKI.
		pki.init({
			ready: loadCertificates,
			defaultError: onWebPkiError,
			restPkiUrl: 'https://restpkiol.azurewebsites.net/'
		});
	}

	// ---------------------------------------------------------------------------------------------
	// Função chamada quando o usuário clica no botão "Atualizar".
	// ---------------------------------------------------------------------------------------------
	function refresh() {
		$.blockUI({message: 'Atualizando ...'});
		loadCertificates();
	}

	// ---------------------------------------------------------------------------------------------
	// Função que carrega os certificados.
	// ---------------------------------------------------------------------------------------------
	function loadCertificates() {
		pki.listCertificates({
			selectId: formElements.certificateSelect.attr('id'),
			selectOptionFormatter: function (cert) {
				var s = cert.subjectName + ' (emitido por ' + cert.issuerName + ')';
				if (new Date() > cert.validityEnd) {
					s = '[EXPIRADO] ' + s;
				}
				return s;
			}
		}).success(function () {
			$.unblockUI();
		});
	}

	// ---------------------------------------------------------------------------------------------
	// Função chamada quando o usuário clica no botão "Assinar Selecionados".
	// ---------------------------------------------------------------------------------------------
	function signBatch() {
		var selectedFiles = formElements.fileList.find('.file-checkbox:checked').map(function () {
			return this.value;
		}).get();

		if (selectedFiles.length === 0) {
			addAlert('warning', 'Por favor, selecione pelo menos um arquivo para assinar.');
			return;
		}

		$.blockUI({message: 'Assinando ...'});

		var selectedCertThumbprint = formElements.certificateSelect.val();

		pki.preauthorizeSignatures({
			certificateThumbprint: selectedCertThumbprint,
			signatureCount: selectedFiles.length
		}).success(function () {
			startBatch(selectedFiles);
		});
	}

	// ---------------------------------------------------------------------------------------------
	// Função chamada quando o usuário autoriza as assinaturas.
	// ---------------------------------------------------------------------------------------------
	function startBatch(filesToSign) {
		// Cria as filas.
		startQueue = new Queue();
		performQueue = new Queue();
		completeQueue = new Queue();

		// Adiciona os arquivos selecionados à primeira fila ("start").
		for (var i = 0; i < filesToSign.length; i++) {
			startQueue.add({index: i, docId: filesToSign[i]});
		}

		// Processa cada fila.
		startQueue.process(startSignature, {threads: 2, output: performQueue});
		performQueue.process(performSignature, {threads: 2, output: completeQueue});
		completeQueue.process(completeSignature, {threads: 2, completed: onBatchCompleted});
	}

	// ---------------------------------------------------------------------------------------------
	// Função que realiza a primeira etapa para cada documento.
	// ---------------------------------------------------------------------------------------------
        function startSignature(step, done) {
            // Encontre a linha da tabela correspondente ao docId
            var row = formElements.fileList.find('input[value="' + step.docId + '"]').closest('tr');

            if (row.length) {
                // Extraia os valores dos campos hidden
                step.crc_arquivo = row.find('input[name="crc_arquivo"]').val();
                step.codigo = row.find('input[name="codigo"]').val();
                step.tipo_doc = row.find('input[name="tipo_doc"]').val();
                step.anexo = row.find('input[name="anexo"]').val();
                step.qtde_assinaturas = row.find('input[name="qtde_assinaturas"]').val();
                step.cod_usuario = row.find('input[name="cod_usuario"]').val();
            } else {
                console.error('Linha da tabela não encontrada para o docId:', step.docId);
                renderFail(step, 'Erro ao obter informações do documento.');
                done();
                return;
            }
	    console.log('Iniciando assinatura para:', 'Documento:', step.docId);
            $.ajax({
                url: step.docId + '/start/',
                method: 'POST',
                dataType: 'json',
                // Se você precisar enviar os valores para o backend na conclusão:
                data: {
                      qtde_assinaturas: step.qtde_assinaturas,
                      crc_arquivo: step.crc_arquivo,
                },
                success: function (token) {
                    step.token = token;
                    done(step);
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    renderFail(step, errorThrown || textStatus);
                    done();
                }
            });
        }

	// ---------------------------------------------------------------------------------------------
	// Função que realiza a segunda etapa para cada documento.
	// ---------------------------------------------------------------------------------------------
	function performSignature(step, done) {
		pki.signWithRestPki({
			token: step.token,
			thumbprint: formElements.certificateSelect.val()
		}).success(function () {
			done(step);
		}).error(function (error) {
			renderFail(step, error);
			done();
		});
	}

	// ---------------------------------------------------------------------------------------------
	// Função que realiza a terceira etapa para cada documento.
	// ---------------------------------------------------------------------------------------------
	function completeSignature(step, done) {
	        console.log('Finalizando assinatura para:', step.docId, 'Codigo:', step.codigo, 'Tipo:', step.tipo_doc, 'Anexo:', step.anexo, 'Usuario:', step.cod_usuario, 'CRC:', step.crc_arquivo);
                $.ajax({
                    url: step.docId + '/complete/' + step.token,
                    method: 'POST',
                    dataType: 'json',
                   // Se você precisar enviar os valores para o backend na conclusão:
                   data: {
                         crc_arquivo: step.crc_arquivo,
                         codigo: step.codigo,
                         tipo_doc: step.tipo_doc,
                         anexo: step.anexo,
                         cod_usuario: step.cod_usuario,
                   },
                   success: function (fileId) {
                       step.fileId = fileId;
                       renderSuccess(step);
                       done(step);
                   },
                   error: function (jqXHR, textStatus, errorThrown) {
                       renderFail(step, errorThrown || textStatus);
                       done();
                   }
                });
	}

	// ---------------------------------------------------------------------------------------------
	// Função chamada quando o lote é concluído.
	// ---------------------------------------------------------------------------------------------
	function onBatchCompleted() {
		addAlert('primary', 'Assinatura em lote concluída');
		$('#processSelectedFiles').prop('disabled', true);
		$.unblockUI();
	}

	// ---------------------------------------------------------------------------------------------
	// Função que renderiza um documento como concluído com sucesso.
	// ---------------------------------------------------------------------------------------------
	function renderSuccess(step) {
		var listItem = formElements.fileList.find('label[for="' + step.docId + '"]').parent();
		listItem
			.append(document.createTextNode(' '))
			.append($('<span />')
				.addClass('fas fa-check text-success'));

		// Remove o checkbox e a label associada
		formElements.fileList.find('input[value="' + step.docId + '"]').remove();
		formElements.fileList.find('label[for="' + step.docId + '"]').remove();
	}

	// ---------------------------------------------------------------------------------------------
	// Função que renderiza um documento como falho.
	// ---------------------------------------------------------------------------------------------
	function renderFail(step, error) {
		addAlert('danger', 'Ocorreu um erro ao assinar o arquivo ' + step.docId + ': ' + error);
		var listItem = formElements.fileList.find('input[value="' + step.docId + '"]').parent();
		listItem
			.append(document.createTextNode(' '))
			.append($('<span />')
				.addClass('fas fa-exclamation text-danger'));
	}

	// ---------------------------------------------------------------------------------------------
	// Função chamada se ocorrer um erro no componente Web PKI.
	// ---------------------------------------------------------------------------------------------
	function onWebPkiError(message, error, origin) {
		$.unblockUI();
		console.log('Ocorreu um erro no componente de assinatura do navegador: ' + message, error);
		addAlert('danger', 'Ocorreu um erro no componente de assinatura do navegador: ' + message);
	}

	// Função auxiliar para adicionar uma mensagem de alerta
	function addAlert(type, message) {
		var alertDiv = $('<div class="alert alert-' + type + ' alert-dismissible fade show" role="alert">' +
			 message +
			'<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close">' +
			'</button>' +
			'</div>');
		$('#alerts').append(alertDiv);
	}

	return {
		init: init
	};

})();
