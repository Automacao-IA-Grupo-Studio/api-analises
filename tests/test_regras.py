import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('analisador', Path(__file__).parents[1]/'services/analisar_job.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class Regras(unittest.TestCase):
    def derivado(self, tipo, media, cnae='0141-5/01'):
        e = next(e for e in a.ELEMENTOS if e['id'] == tipo)
        return a._calcular_derivado(e, [{'id':'faturamento','dados':{'media':media}}], {'cnae_principal':cnae})

    def test_limites(self):
        self.assertTrue(self.derivado('fastpass',200_000_000).startswith('Inconclusivo'))
        self.assertTrue(self.derivado('fastpass',200_000_001).startswith('Sim'))
        self.assertTrue(self.derivado('finap',50_000_000).startswith('Não'))
        self.assertTrue(self.derivado('finap',50_000_001).startswith('Sim'))
        self.assertTrue(self.derivado('finap',50_000_001,'9999-9/99').startswith('Não'))
        self.assertTrue(self.derivado('supply',30_000_000).startswith('Sim'))

    def test_media_e_somente_leitura(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'B - Documentos'/'1 - Contábil'/'5 - ECF';d.mkdir(parents=True)
            for ano,valor in [(2024,'100.000.000,00'),(2025,'200.000.000,00'),(2026,'900.000.000,00')]:
                (d/f'{ano}.txt').write_text(f'TOTAL DO ARQUIVO: {valor}')
            before={str(p):p.read_bytes() for p in d.iterdir()}
            e=next(e for e in a.ELEMENTOS if e['id']=='faturamento')
            result=a._proc_faturamento(tmp,e,{})
            self.assertEqual(result['dados']['media'],150_000_000)
            self.assertEqual(len(result['dados']['por_ano']),3)
            self.assertEqual(len(result['dados']['evidencias']),3)
            self.assertEqual(before,{str(p):p.read_bytes() for p in d.iterdir()})
            (d/'duplicado2025.txt').write_text('TOTAL DO ARQUIVO: 300.000.000,00')
            self.assertIsNone(a._proc_faturamento(tmp,e,{})['dados']['media'])

    def test_transacao(self):
        e=next(e for e in a.ELEMENTOS if e['id']=='regularize')
        for valor,esperado in [('600.000,00',False),('600.000,01',True)]:
            with patch.object(a,'candidatos',return_value=['x.pdf']), patch.object(a,'extrair_texto',return_value=f'capacidade de pagamento\nValor total da dívida na PGFN e RFB: R$ {valor}'):
                self.assertEqual(a._proc_regularize('',e,{})['dados']['dentro'],esperado)

    def test_family(self):
        e=next(e for e in a.ELEMENTOS if e['id']=='socios')
        texto='CNPJ: 11.111.111/0001-11\nSócios e Administradores\n123.456.789-00 MARIA SILVA\n22.222.222/0001-22 EMPRESA SOCIA\nPendências\n333.333.333-33 TERCEIRO'
        with patch.object(a,'_varrer_pasta',return_value=['fiscal.pdf']),patch.object(a,'extrair_texto',return_value=texto):
            r=a._proc_qsa('',e,{})
            self.assertEqual([x['tipo'] for x in r['dados']['socios']],['CPF','CNPJ'])
            self.assertEqual(len(r['dados']['evidencias']),2)

    def test_simples_historico(self):
        e=next(e for e in a.ELEMENTOS if e['id']=='simples_nacional')
        t='Situação no Simples Nacional: NÃO OPTANTE\nPeríodos anteriores no Simples Nacional\n01/01/2020 a 31/12/2022'
        with patch.object(a,'candidatos',return_value=['simples.pdf']),patch.object(a,'extrair_texto',return_value=t):
            self.assertEqual(a._proc_simples('',e,{})['dados']['anos_optante'],[2020,2021,2022])

if __name__=='__main__': unittest.main()
