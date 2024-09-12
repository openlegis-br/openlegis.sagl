$(document).ready(function(){$.fn.dataTable.moment( 'DD/MM/YYYY HH:mm:ss');$.fn.dataTable.moment('DD/MM/YYYY');$("#datatable").DataTable({language: {url: '../../assets/libs/datatables.net/plugins/i18n/pt-BR.json'}}),$(".datatable").DataTable({language: {url: '../../assets/libs/datatables.net/plugins/i18n/pt-BR.json'}}),$("#datatable-buttons").DataTable({lengthChange:!1,buttons:["copy","excel","pdf","colvis"]}).buttons().container().appendTo("#datatable-buttons_wrapper .col-md-6:eq(0)"),$("#datatable2").DataTable({language: {url: '../../assets/libs/datatables.net/plugins/i18n/pt-BR.json'}}),$(".dataTables_length select").addClass("form-select form-select-sm")});

$(document).ready(function(){
   $.fn.dataTable.moment( 'DD/MM/YYYY HH:mm:ss');
   $.fn.dataTable.moment('DD/MM/YYYY');
   $(".datatable-reverse").DataTable({
      language: {url: '../../assets/libs/datatables.net/plugins/i18n/pt-BR.json'},
      order: [[1, 'desc'], [0, 'desc']]
   }) 
});

$(document).ready(function(){
   $.fn.dataTable.moment( 'DD/MM/YYYY HH:mm:ss');
   $.fn.dataTable.moment('DD/MM/YYYY');
   $(".datatable-tramitacao").DataTable({
      language: {url: '../../assets/libs/datatables.net/plugins/i18n/pt-BR.json'},
      order: [[0, 'desc']]
   }) 
});
