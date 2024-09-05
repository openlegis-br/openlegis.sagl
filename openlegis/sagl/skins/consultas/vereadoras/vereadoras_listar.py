from DateTime import DateTime

lst_vereadoras = []
for vereadora in context.consultas.vereadoras.vereadoras_obter_zsql():
    dic_vereadora = {
         'cod_parlamentar': vereadora.cod_parlamentar,
         'nome_completo': vereadora.nom_completo,
         'nome_parlamentar': vereadora.nom_parlamentar
    }
    lst_legislaturas = []
    for mandato in context.zsql.mandato_obter_zsql(cod_parlamentar=vereadora.cod_parlamentar):
        legislatura = context.zsql.legislatura_obter_zsql(num_legislatura=mandato.num_legislatura)[0]
        dic_legislatura = {
           'cod_parlamentar': mandato.cod_parlamentar,
           'num_legislatura': legislatura.num_legislatura,
           'inicio': DateTime(legislatura.dat_inicio, datefmt='international').strftime('%Y'),
           'fim': DateTime(legislatura.dat_fim, datefmt='international').strftime('%Y')
        }
        lst_legislaturas.append(dic_legislatura)
    for item in lst_legislaturas:
        if vereadora.cod_parlamentar == item['cod_parlamentar']:
           dic_vereadora['ult_legislatura'] = str(item.get('num_legislatura',item))
        break
    dic_vereadora['legislaturas'] = lst_legislaturas
    lst_vereadoras.append(dic_vereadora)

lst_vereadoras.sort(key=lambda dic: int(dic['ult_legislatura']), reverse=True)

return lst_vereadoras
