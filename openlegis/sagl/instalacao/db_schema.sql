SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Banco de dados: `openlegis`
--

-- --------------------------------------------------------

--
-- Estrutura para tabela `acomp_materia`
--

CREATE TABLE `acomp_materia` (
  `cod_cadastro` int NOT NULL,
  `cod_materia` int NOT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_hash` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `afastamento`
--

CREATE TABLE `afastamento` (
  `cod_afastamento` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_mandato` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `tip_afastamento` int NOT NULL,
  `dat_inicio_afastamento` date NOT NULL,
  `dat_fim_afastamento` date DEFAULT NULL,
  `cod_parlamentar_suplente` int NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `anexada`
--

CREATE TABLE `anexada` (
  `id` int NOT NULL,
  `cod_materia_principal` int NOT NULL,
  `cod_materia_anexada` int NOT NULL,
  `dat_anexacao` date NOT NULL,
  `dat_desanexacao` date DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `anexo_norma`
--

CREATE TABLE `anexo_norma` (
  `cod_anexo` int NOT NULL,
  `cod_norma` int NOT NULL,
  `txt_descricao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_armario`
--

CREATE TABLE `arquivo_armario` (
  `cod_armario` int NOT NULL,
  `cod_corredor` int DEFAULT NULL,
  `cod_unidade` int NOT NULL,
  `nom_armario` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_corredor`
--

CREATE TABLE `arquivo_corredor` (
  `cod_corredor` int NOT NULL,
  `cod_unidade` int NOT NULL,
  `nom_corredor` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_item`
--

CREATE TABLE `arquivo_item` (
  `cod_item` int NOT NULL,
  `cod_recipiente` int NOT NULL,
  `tip_suporte` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_norma` int DEFAULT NULL,
  `cod_documento` int DEFAULT NULL,
  `cod_protocolo` int(7) UNSIGNED ZEROFILL DEFAULT NULL,
  `des_item` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_arquivamento` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_prateleira`
--

CREATE TABLE `arquivo_prateleira` (
  `cod_prateleira` int NOT NULL,
  `cod_armario` int DEFAULT NULL,
  `cod_corredor` int DEFAULT NULL,
  `cod_unidade` int NOT NULL,
  `nom_prateleira` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_recipiente`
--

CREATE TABLE `arquivo_recipiente` (
  `cod_recipiente` int NOT NULL,
  `tip_recipiente` int NOT NULL,
  `num_recipiente` varchar(11) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tip_tit_documental` int NOT NULL,
  `ano_recipiente` smallint NOT NULL,
  `dat_recipiente` date NOT NULL,
  `cod_corredor` int DEFAULT NULL,
  `cod_armario` int DEFAULT NULL,
  `cod_prateleira` int DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `num_folha_recipiente` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_tipo_recipiente`
--

CREATE TABLE `arquivo_tipo_recipiente` (
  `tip_recipiente` int NOT NULL,
  `des_tipo_recipiente` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_tipo_suporte`
--

CREATE TABLE `arquivo_tipo_suporte` (
  `tip_suporte` int NOT NULL,
  `des_tipo_suporte` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_tipo_tit_documental`
--

CREATE TABLE `arquivo_tipo_tit_documental` (
  `tip_tit_documental` int NOT NULL,
  `sgl_tip_tit_documental` varchar(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_tipo_tit_documental` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `arquivo_unidade`
--

CREATE TABLE `arquivo_unidade` (
  `cod_unidade` int NOT NULL,
  `tip_extensao_atuacao` int NOT NULL,
  `tip_estagio_evolucao` int NOT NULL,
  `nom_unidade` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_localizacao` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `assessor_parlamentar`
--

CREATE TABLE `assessor_parlamentar` (
  `cod_assessor` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `nom_assessor` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_cargo` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `num_cpf` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_rg` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_residencial` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_cep_resid` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_resid` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_celular` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_nomeacao` date NOT NULL,
  `dat_exoneracao` date DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `col_username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `assinatura_documento`
--

CREATE TABLE `assinatura_documento` (
  `id` int NOT NULL,
  `cod_assinatura_doc` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `codigo` int NOT NULL,
  `anexo` int DEFAULT NULL,
  `tipo_doc` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `dat_solicitacao` datetime NOT NULL,
  `cod_usuario` int NOT NULL,
  `dat_assinatura` datetime DEFAULT NULL,
  `dat_recusa` datetime DEFAULT NULL,
  `ind_assinado` tinyint NOT NULL DEFAULT '0',
  `ind_recusado` tinyint NOT NULL DEFAULT '0',
  `ind_separado` tinyint NOT NULL DEFAULT '0',
  `txt_motivo_recusa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_prim_assinatura` tinyint NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `assinatura_storage`
--

CREATE TABLE `assinatura_storage` (
  `id` int NOT NULL,
  `tip_documento` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pdf_location` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `storage_path` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pdf_file` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pdf_signed` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `assunto_materia`
--

CREATE TABLE `assunto_materia` (
  `cod_assunto` int NOT NULL,
  `des_assunto` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_estendida` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `assunto_norma`
--

CREATE TABLE `assunto_norma` (
  `cod_assunto` int NOT NULL,
  `des_assunto` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_estendida` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `assunto_proposicao`
--

CREATE TABLE `assunto_proposicao` (
  `cod_assunto` int NOT NULL,
  `tip_proposicao` int NOT NULL,
  `des_assunto` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nom_orgao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `end_orgao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `autor`
--

CREATE TABLE `autor` (
  `cod_autor` int NOT NULL,
  `cod_partido` int DEFAULT NULL,
  `cod_comissao` int DEFAULT NULL,
  `cod_bancada` int DEFAULT NULL,
  `cod_parlamentar` int DEFAULT NULL,
  `tip_autor` tinyint NOT NULL,
  `nom_autor` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `col_username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `autoria`
--

CREATE TABLE `autoria` (
  `id` int NOT NULL,
  `cod_autor` int NOT NULL,
  `cod_materia` int NOT NULL,
  `ind_primeiro_autor` tinyint NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `autoria_emenda`
--

CREATE TABLE `autoria_emenda` (
  `id` int NOT NULL,
  `cod_autor` int NOT NULL,
  `cod_emenda` int NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `autoria_substitutivo`
--

CREATE TABLE `autoria_substitutivo` (
  `id` int NOT NULL,
  `cod_autor` int NOT NULL,
  `cod_substitutivo` int NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `bancada`
--

CREATE TABLE `bancada` (
  `cod_bancada` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `cod_partido` int DEFAULT NULL,
  `nom_bancada` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `descricao` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_criacao` date DEFAULT NULL,
  `dat_extincao` date DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `cargo_bancada`
--

CREATE TABLE `cargo_bancada` (
  `cod_cargo` tinyint NOT NULL,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unico` tinyint NOT NULL DEFAULT '0',
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `cargo_comissao`
--

CREATE TABLE `cargo_comissao` (
  `cod_cargo` int NOT NULL,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unico` int NOT NULL DEFAULT '0',
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `cargo_executivo`
--

CREATE TABLE `cargo_executivo` (
  `cod_cargo` tinyint NOT NULL,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `cargo_mesa`
--

CREATE TABLE `cargo_mesa` (
  `cod_cargo` int NOT NULL,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unico` int NOT NULL DEFAULT '1',
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `categoria_instituicao`
--

CREATE TABLE `categoria_instituicao` (
  `tip_instituicao` int NOT NULL,
  `cod_categoria` int NOT NULL,
  `des_categoria` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `coautoria_proposicao`
--

CREATE TABLE `coautoria_proposicao` (
  `id` int NOT NULL,
  `cod_proposicao` int NOT NULL,
  `cod_autor` int NOT NULL,
  `ind_aderido` tinyint NOT NULL DEFAULT '0',
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `coligacao`
--

CREATE TABLE `coligacao` (
  `cod_coligacao` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `nom_coligacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_votos_coligacao` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `comissao`
--

CREATE TABLE `comissao` (
  `cod_comissao` int NOT NULL,
  `tip_comissao` int NOT NULL,
  `nom_comissao` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_comissao` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_criacao` date NOT NULL,
  `dat_extincao` date DEFAULT NULL,
  `nom_apelido_temp` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_instalacao_temp` date DEFAULT NULL,
  `dat_final_prevista_temp` date DEFAULT NULL,
  `dat_prorrogada_temp` date DEFAULT NULL,
  `dat_fim_comissao` date DEFAULT NULL,
  `nom_secretario` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_reuniao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_secretaria` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_secretaria` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_fax_secretaria` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_agenda_reuniao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `loc_reuniao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_finalidade` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unid_deliberativa` int NOT NULL,
  `ordem` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `composicao_bancada`
--

CREATE TABLE `composicao_bancada` (
  `cod_comp_bancada` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_bancada` int NOT NULL,
  `cod_periodo_comp` int DEFAULT NULL,
  `cod_cargo` tinyint NOT NULL,
  `ind_titular` tinyint NOT NULL,
  `dat_designacao` date NOT NULL,
  `dat_desligamento` date DEFAULT NULL,
  `des_motivo_desligamento` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `obs_composicao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `composicao_coligacao`
--

CREATE TABLE `composicao_coligacao` (
  `id` int NOT NULL,
  `cod_partido` int NOT NULL,
  `cod_coligacao` int NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `composicao_comissao`
--

CREATE TABLE `composicao_comissao` (
  `cod_comp_comissao` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_comissao` int NOT NULL,
  `cod_periodo_comp` int NOT NULL,
  `cod_cargo` int NOT NULL,
  `ind_titular` int NOT NULL DEFAULT '1',
  `dat_designacao` date NOT NULL,
  `dat_desligamento` date DEFAULT NULL,
  `des_motivo_desligamento` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `obs_composicao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `composicao_executivo`
--

CREATE TABLE `composicao_executivo` (
  `cod_composicao` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `nom_completo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_cargo` tinyint NOT NULL,
  `cod_partido` int DEFAULT NULL,
  `dat_inicio_mandato` date DEFAULT NULL,
  `dat_fim_mandato` date DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `composicao_mesa`
--

CREATE TABLE `composicao_mesa` (
  `id` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_sessao_leg` int DEFAULT NULL,
  `cod_periodo_comp` int NOT NULL,
  `cod_cargo` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `dependente`
--

CREATE TABLE `dependente` (
  `cod_dependente` int NOT NULL,
  `tip_dependente` tinyint NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `nom_dependente` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sex_dependente` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `num_cpf` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_rg` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `despacho_inicial`
--

CREATE TABLE `despacho_inicial` (
  `id` int NOT NULL,
  `cod_materia` int NOT NULL,
  `num_ordem` tinyint UNSIGNED NOT NULL,
  `cod_comissao` int NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `destinatario_oficio`
--

CREATE TABLE `destinatario_oficio` (
  `cod_destinatario` int NOT NULL,
  `cod_documento` int NOT NULL,
  `cod_instituicao` int NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `documento_acessorio`
--

CREATE TABLE `documento_acessorio` (
  `cod_documento` int NOT NULL,
  `cod_materia` int NOT NULL,
  `tip_documento` int NOT NULL,
  `nom_documento` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_documento` datetime DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `nom_autor_documento` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_publico` tinyint NOT NULL DEFAULT '1',
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `documento_acessorio_administrativo`
--

CREATE TABLE `documento_acessorio_administrativo` (
  `cod_documento_acessorio` int NOT NULL,
  `cod_documento` int NOT NULL DEFAULT '0',
  `tip_documento` int NOT NULL DEFAULT '0',
  `nom_documento` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_arquivo` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_documento` datetime DEFAULT NULL,
  `nom_autor_documento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_assunto` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `documento_administrativo`
--

CREATE TABLE `documento_administrativo` (
  `cod_documento` int NOT NULL,
  `tip_documento` int NOT NULL,
  `num_documento` int NOT NULL,
  `ano_documento` smallint NOT NULL DEFAULT '0',
  `dat_documento` date NOT NULL,
  `num_protocolo` int DEFAULT NULL,
  `txt_interessado` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_autor` int DEFAULT NULL,
  `cod_entidade` int DEFAULT NULL,
  `cod_materia` int DEFAULT NULL,
  `num_dias_prazo` tinyint DEFAULT NULL,
  `dat_fim_prazo` date DEFAULT NULL,
  `ind_tramitacao` tinyint NOT NULL DEFAULT '0',
  `txt_assunto` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `cod_situacao` int DEFAULT NULL,
  `cod_assunto` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `documento_administrativo_materia`
--

CREATE TABLE `documento_administrativo_materia` (
  `cod_vinculo` int NOT NULL,
  `cod_documento` int NOT NULL,
  `cod_materia` int NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `documento_administrativo_vinculado`
--

CREATE TABLE `documento_administrativo_vinculado` (
  `cod_vinculo` int NOT NULL,
  `cod_documento_vinculante` int NOT NULL,
  `cod_documento_vinculado` int NOT NULL,
  `dat_vinculacao` datetime DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `documento_comissao`
--

CREATE TABLE `documento_comissao` (
  `cod_documento` int NOT NULL,
  `cod_comissao` int NOT NULL,
  `dat_documento` date NOT NULL,
  `txt_descricao` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `emenda`
--

CREATE TABLE `emenda` (
  `cod_emenda` int NOT NULL,
  `tip_emenda` int NOT NULL,
  `num_emenda` int NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_autor` int DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `exc_pauta` tinyint DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `encerramento_presenca`
--

CREATE TABLE `encerramento_presenca` (
  `cod_presenca_encerramento` int NOT NULL,
  `cod_sessao_plen` int NOT NULL DEFAULT '0',
  `cod_parlamentar` int NOT NULL,
  `dat_ordem` date NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `expediente_discussao`
--

CREATE TABLE `expediente_discussao` (
  `id` int NOT NULL,
  `cod_ordem` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `expediente_materia`
--

CREATE TABLE `expediente_materia` (
  `cod_ordem` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_parecer` int DEFAULT NULL,
  `dat_ordem` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `num_ordem` int DEFAULT NULL,
  `txt_resultado` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `tip_turno` int DEFAULT NULL,
  `tip_votacao` int NOT NULL,
  `tip_quorum` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `expediente_presenca`
--

CREATE TABLE `expediente_presenca` (
  `cod_presenca_expediente` int NOT NULL,
  `cod_sessao_plen` int NOT NULL DEFAULT '0',
  `cod_parlamentar` int NOT NULL,
  `dat_ordem` date NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `expediente_sessao_plenaria`
--

CREATE TABLE `expediente_sessao_plenaria` (
  `id` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_expediente` int NOT NULL,
  `txt_expediente` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `filiacao`
--

CREATE TABLE `filiacao` (
  `id` int NOT NULL,
  `dat_filiacao` date NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_partido` int NOT NULL,
  `dat_desfiliacao` date DEFAULT NULL,
  `ind_excluido` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `funcionario`
--

CREATE TABLE `funcionario` (
  `cod_funcionario` int NOT NULL,
  `nom_funcionario` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_usuario` int DEFAULT NULL,
  `des_cargo` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_cadastro` date NOT NULL,
  `ind_ativo` tinyint NOT NULL DEFAULT '1',
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `gabinete_atendimento`
--

CREATE TABLE `gabinete_atendimento` (
  `cod_atendimento` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_eleitor` int NOT NULL,
  `dat_atendimento` date NOT NULL,
  `txt_assunto` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `dat_resultado` date DEFAULT NULL,
  `txt_resultado` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_atendente` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `gabinete_eleitor`
--

CREATE TABLE `gabinete_eleitor` (
  `cod_eleitor` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `dat_cadastro` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `nom_eleitor` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sex_eleitor` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `des_estado_civil` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `doc_identidade` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_cpf` varchar(50) CHARACTER SET utf32 COLLATE utf32_unicode_ci DEFAULT NULL,
  `txt_classe` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_profissao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_escolaridade` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_residencial` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_bairro` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_cep` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_localidade` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_uf` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_telefone` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_celular` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_conjuge` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_dependentes` tinytext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `des_local_trabalho` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_atualizacao` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `cod_assessor` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `instituicao`
--

CREATE TABLE `instituicao` (
  `cod_instituicao` int NOT NULL,
  `tip_instituicao` int NOT NULL,
  `cod_categoria` int NOT NULL,
  `nom_instituicao` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_instituicao` tinytext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `nom_bairro` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_localidade` int DEFAULT NULL,
  `num_cep` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_telefone` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_fax` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_web` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_responsavel` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_cargo` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_forma_tratamento` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` tinytext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0',
  `dat_insercao` datetime DEFAULT NULL,
  `txt_user_insercao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ip_insercao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `timestamp_alteracao` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `txt_user_alteracao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ip_alteracao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `legislacao_citada`
--

CREATE TABLE `legislacao_citada` (
  `id` int NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_norma` int NOT NULL,
  `des_disposicoes` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_parte` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_livro` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_titulo` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_capitulo` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_secao` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_subsecao` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_artigo` varchar(4) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_paragrafo` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_inciso` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_alinea` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_item` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `legislatura`
--

CREATE TABLE `legislatura` (
  `id` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `dat_inicio` date NOT NULL,
  `dat_fim` date NOT NULL,
  `dat_eleicao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `lexml_registro_provedor`
--

CREATE TABLE `lexml_registro_provedor` (
  `cod_provedor` int NOT NULL,
  `id_provedor` int NOT NULL,
  `nom_provedor` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_provedor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `adm_email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_responsavel` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_responsavel` int DEFAULT NULL,
  `xml_provedor` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `lexml_registro_publicador`
--

CREATE TABLE `lexml_registro_publicador` (
  `cod_publicador` int NOT NULL,
  `id_publicador` int NOT NULL,
  `nom_publicador` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `adm_email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sigla` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_responsavel` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_responsavel` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `liderancas_partidarias`
--

CREATE TABLE `liderancas_partidarias` (
  `id` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_partido` int NOT NULL,
  `num_ordem` tinyint NOT NULL,
  `url_discurso` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `localidade`
--

CREATE TABLE `localidade` (
  `cod_localidade` int NOT NULL DEFAULT '0',
  `nom_localidade` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_localidade_pesq` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_localidade` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_uf` char(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_regiao` char(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `logradouro`
--

CREATE TABLE `logradouro` (
  `cod_logradouro` int NOT NULL,
  `nom_logradouro` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nom_bairro` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_cep` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_localidade` int DEFAULT NULL,
  `cod_norma` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `mandato`
--

CREATE TABLE `mandato` (
  `cod_mandato` int NOT NULL,
  `num_legislatura` int NOT NULL DEFAULT '0',
  `cod_coligacao` int DEFAULT NULL,
  `dat_inicio_mandato` date DEFAULT NULL,
  `tip_causa_fim_mandato` int DEFAULT NULL,
  `dat_fim_mandato` date DEFAULT NULL,
  `num_votos_recebidos` int DEFAULT NULL,
  `dat_expedicao_diploma` date DEFAULT NULL,
  `cod_parlamentar` int NOT NULL DEFAULT '0',
  `tip_afastamento` int DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_titular` tinyint NOT NULL DEFAULT '1',
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `materia_apresentada_sessao`
--

CREATE TABLE `materia_apresentada_sessao` (
  `cod_ordem` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_emenda` int DEFAULT NULL,
  `cod_substitutivo` int DEFAULT NULL,
  `cod_parecer` int DEFAULT NULL,
  `cod_doc_acessorio` int DEFAULT NULL,
  `cod_documento` int DEFAULT NULL,
  `dat_ordem` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `num_ordem` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `materia_legislativa`
--

CREATE TABLE `materia_legislativa` (
  `cod_materia` int NOT NULL,
  `tip_id_basica` int NOT NULL,
  `num_protocolo` int DEFAULT NULL,
  `num_ident_basica` int NOT NULL,
  `ano_ident_basica` smallint NOT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `tip_apresentacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_regime_tramitacao` tinyint NOT NULL,
  `dat_publicacao` date DEFAULT NULL,
  `des_veiculo_publicacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_origem_externa` int DEFAULT NULL,
  `num_origem_externa` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ano_origem_externa` smallint DEFAULT NULL,
  `dat_origem_externa` date DEFAULT NULL,
  `cod_local_origem_externa` int DEFAULT NULL,
  `nom_apelido` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_dias_prazo` tinyint DEFAULT NULL,
  `dat_fim_prazo` date DEFAULT NULL,
  `ind_tramitacao` tinyint NOT NULL,
  `ind_polemica` tinyint DEFAULT NULL,
  `des_objeto` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_complementar` tinyint DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `tip_quorum` int DEFAULT NULL,
  `cod_situacao` int DEFAULT NULL,
  `cod_assunto` int DEFAULT NULL,
  `cod_materia_principal` int DEFAULT NULL,
  `autografo_numero` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `autografo_data` date DEFAULT NULL,
  `data_encerramento` date DEFAULT NULL,
  `materia_num_tipo_status` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `mesa_sessao_plenaria`
--

CREATE TABLE `mesa_sessao_plenaria` (
  `id` int NOT NULL,
  `cod_cargo` int NOT NULL,
  `cod_sessao_leg` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `ind_excluido` tinyint UNSIGNED DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `nivel_instrucao`
--

CREATE TABLE `nivel_instrucao` (
  `cod_nivel_instrucao` tinyint NOT NULL,
  `des_nivel_instrucao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `norma_juridica`
--

CREATE TABLE `norma_juridica` (
  `cod_norma` int NOT NULL,
  `tip_norma` tinyint NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `num_norma` int NOT NULL,
  `ano_norma` smallint NOT NULL,
  `tip_esfera_federacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_norma` date DEFAULT NULL,
  `dat_publicacao` date DEFAULT NULL,
  `des_veiculo_publicacao` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_pag_inicio_publ` int DEFAULT NULL,
  `num_pag_fim_publ` int DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_complemento` tinyint DEFAULT NULL,
  `cod_assunto` char(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_situacao` int DEFAULT NULL,
  `dat_vigencia` date DEFAULT NULL,
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `ind_publico` int NOT NULL DEFAULT '0',
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `numeracao`
--

CREATE TABLE `numeracao` (
  `id` int NOT NULL,
  `cod_materia` int NOT NULL,
  `num_ordem` int NOT NULL,
  `tip_materia` int NOT NULL,
  `num_materia` int NOT NULL,
  `ano_materia` int NOT NULL,
  `dat_materia` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `oradores`
--

CREATE TABLE `oradores` (
  `id` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `num_ordem` tinyint NOT NULL,
  `url_discurso` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `oradores_expediente`
--

CREATE TABLE `oradores_expediente` (
  `id` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `num_ordem` tinyint NOT NULL,
  `url_discurso` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `ordem_dia`
--

CREATE TABLE `ordem_dia` (
  `cod_ordem` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_parecer` int DEFAULT NULL,
  `dat_ordem` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `num_ordem` int DEFAULT NULL,
  `txt_resultado` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `tip_turno` int DEFAULT NULL,
  `tip_votacao` int NOT NULL,
  `tip_quorum` int DEFAULT NULL,
  `urgencia` tinyint DEFAULT NULL,
  `tipo_discussao_ordem` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `ordem_dia_discussao`
--

CREATE TABLE `ordem_dia_discussao` (
  `id` int NOT NULL,
  `cod_ordem` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `ordem_dia_presenca`
--

CREATE TABLE `ordem_dia_presenca` (
  `cod_presenca_ordem_dia` int NOT NULL,
  `cod_sessao_plen` int NOT NULL DEFAULT '0',
  `cod_parlamentar` int NOT NULL,
  `tip_frequencia` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'P',
  `txt_justif_ausencia` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_ordem` date NOT NULL,
  `flag_presenca` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `orgao`
--

CREATE TABLE `orgao` (
  `cod_orgao` int NOT NULL,
  `nom_orgao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sgl_orgao` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unid_deliberativa` int NOT NULL DEFAULT '0',
  `end_orgao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_orgao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `origem`
--

CREATE TABLE `origem` (
  `cod_origem` int NOT NULL,
  `sgl_origem` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_origem` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `parecer`
--

CREATE TABLE `parecer` (
  `cod_relatoria` int NOT NULL,
  `num_parecer` smallint DEFAULT NULL,
  `ano_parecer` smallint DEFAULT NULL,
  `cod_materia` int NOT NULL,
  `tip_conclusao` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_apresentacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_parecer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `parlamentar`
--

CREATE TABLE `parlamentar` (
  `cod_parlamentar` int NOT NULL,
  `nom_completo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_parlamentar` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_painel` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sex_parlamentar` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `dat_falecimento` date DEFAULT NULL,
  `num_cpf` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_rg` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_situacao_militar` tinyint DEFAULT NULL,
  `cod_nivel_instrucao` tinyint DEFAULT NULL,
  `des_curso` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_casa` int DEFAULT NULL,
  `num_gab_parlamentar` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_parlamentar` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_fax_parlamentar` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_residencial` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_localidade_resid` int DEFAULT NULL,
  `num_cep_resid` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_resid` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_celular` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_fax_resid` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_web` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_profissao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_local_atuacao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_ativo` tinyint NOT NULL DEFAULT '0',
  `ind_unid_deliberativa` tinyint DEFAULT NULL,
  `txt_biografia` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `texto_parlamentar` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `partido`
--

CREATE TABLE `partido` (
  `cod_partido` int NOT NULL,
  `sgl_partido` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_partido` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_criacao` date DEFAULT NULL,
  `dat_extincao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `periodo_comp_bancada`
--

CREATE TABLE `periodo_comp_bancada` (
  `cod_periodo_comp` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `dat_inicio_periodo` date NOT NULL,
  `dat_fim_periodo` date NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `periodo_comp_comissao`
--

CREATE TABLE `periodo_comp_comissao` (
  `cod_periodo_comp` int NOT NULL,
  `dat_inicio_periodo` date NOT NULL,
  `dat_fim_periodo` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `periodo_comp_mesa`
--

CREATE TABLE `periodo_comp_mesa` (
  `cod_periodo_comp` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `dat_inicio_periodo` date NOT NULL,
  `dat_fim_periodo` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `periodo_sessao`
--

CREATE TABLE `periodo_sessao` (
  `cod_periodo` int NOT NULL,
  `num_periodo` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `cod_sessao_leg` int NOT NULL,
  `tip_sessao` tinyint NOT NULL,
  `dat_inicio` date NOT NULL,
  `dat_fim` date NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `pessoa`
--

CREATE TABLE `pessoa` (
  `cod_pessoa` int NOT NULL,
  `nom_pessoa` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `doc_identidade` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `sex_pessoa` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_estado_civil` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_conjuge` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_dependentes` tinytext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_logradouro` int DEFAULT NULL,
  `end_residencial` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `num_imovel` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_complemento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_bairro` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `num_cep` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nom_cidade` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sgl_uf` varchar(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tempo_residencia` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_telefone` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_celular` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_profissao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_local_trabalho` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_atualizacao` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `peticao`
--

CREATE TABLE `peticao` (
  `cod_peticao` int NOT NULL,
  `tip_peticionamento` int NOT NULL,
  `txt_descricao` varchar(400) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_usuario` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_doc_acessorio` int DEFAULT NULL,
  `cod_documento` int DEFAULT NULL,
  `cod_documento_vinculado` int DEFAULT NULL,
  `cod_norma` int DEFAULT NULL,
  `num_norma` int DEFAULT NULL,
  `ano_norma` int DEFAULT NULL,
  `dat_norma` date DEFAULT NULL,
  `dat_envio` datetime DEFAULT NULL,
  `dat_recebimento` datetime DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `txt_observacao` mediumtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `proposicao`
--

CREATE TABLE `proposicao` (
  `cod_proposicao` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_autor` int NOT NULL,
  `tip_proposicao` int NOT NULL,
  `dat_envio` datetime DEFAULT NULL,
  `dat_recebimento` datetime DEFAULT NULL,
  `txt_descricao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_mat_ou_doc` int DEFAULT NULL,
  `cod_emenda` int DEFAULT NULL,
  `cod_substitutivo` int DEFAULT NULL,
  `cod_parecer` int DEFAULT NULL,
  `dat_solicitacao_devolucao` datetime DEFAULT NULL,
  `dat_devolucao` datetime DEFAULT NULL,
  `txt_justif_devolucao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `cod_assessor` int DEFAULT NULL,
  `cod_assunto` int DEFAULT NULL,
  `ind_excluido` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `proposicao_geocode`
--

CREATE TABLE `proposicao_geocode` (
  `id` int NOT NULL,
  `cod_proposicao` int NOT NULL,
  `endereco` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `lat` decimal(18,14) NOT NULL,
  `lng` decimal(18,13) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `protocolo`
--

CREATE TABLE `protocolo` (
  `cod_protocolo` int(7) UNSIGNED ZEROFILL NOT NULL,
  `num_protocolo` int(7) UNSIGNED ZEROFILL DEFAULT NULL,
  `ano_protocolo` smallint NOT NULL,
  `dat_protocolo` date NOT NULL,
  `hor_protocolo` time NOT NULL DEFAULT '00:00:00',
  `dat_timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `tip_protocolo` int NOT NULL,
  `tip_processo` int DEFAULT NULL,
  `txt_interessado` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_autor` int DEFAULT NULL,
  `cod_entidade` int DEFAULT NULL,
  `txt_assunto_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `tip_documento` int DEFAULT NULL,
  `tip_materia` int DEFAULT NULL,
  `tip_natureza_materia` smallint DEFAULT NULL,
  `cod_materia_principal` int DEFAULT NULL,
  `num_paginas` int DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_anulado` tinyint NOT NULL DEFAULT '0',
  `txt_user_protocolo` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_user_anulacao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ip_anulacao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_just_anulacao` varchar(400) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `timestamp_anulacao` datetime DEFAULT NULL,
  `codigo_acesso` varchar(18) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `quorum_votacao`
--

CREATE TABLE `quorum_votacao` (
  `cod_quorum` int NOT NULL,
  `des_quorum` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_formula` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `regime_tramitacao`
--

CREATE TABLE `regime_tramitacao` (
  `cod_regime_tramitacao` tinyint NOT NULL,
  `des_regime_tramitacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `registro_votacao`
--

CREATE TABLE `registro_votacao` (
  `cod_votacao` int NOT NULL,
  `tip_resultado_votacao` int UNSIGNED NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_parecer` int DEFAULT NULL,
  `cod_ordem` int NOT NULL,
  `cod_emenda` int DEFAULT NULL,
  `cod_subemenda` int DEFAULT NULL,
  `cod_substitutivo` int DEFAULT NULL,
  `num_votos_sim` tinyint UNSIGNED NOT NULL,
  `num_votos_nao` tinyint UNSIGNED NOT NULL,
  `num_abstencao` tinyint UNSIGNED NOT NULL,
  `num_ausentes` tinyint UNSIGNED DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_obs_anterior` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `registro_votacao_parlamentar`
--

CREATE TABLE `registro_votacao_parlamentar` (
  `cod_votacao` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `vot_parlamentar` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `relatoria`
--

CREATE TABLE `relatoria` (
  `cod_relatoria` int NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `tip_fim_relatoria` tinyint DEFAULT NULL,
  `cod_comissao` int DEFAULT NULL,
  `num_ordem` tinyint NOT NULL,
  `dat_desig_relator` date NOT NULL,
  `dat_destit_relator` datetime DEFAULT NULL,
  `tip_apresentacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_parecer` int DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `ano_parecer` smallint DEFAULT NULL,
  `txt_parecer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `tip_conclusao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `reuniao_comissao`
--

CREATE TABLE `reuniao_comissao` (
  `cod_reuniao` int NOT NULL,
  `cod_comissao` int NOT NULL,
  `num_reuniao` int NOT NULL,
  `des_tipo_reuniao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_tema` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_inicio_reuniao` date NOT NULL,
  `hr_inicio_reuniao` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hr_fim_reuniao` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `url_video` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `reuniao_comissao_pauta`
--

CREATE TABLE `reuniao_comissao_pauta` (
  `cod_item` int NOT NULL,
  `cod_reuniao` int NOT NULL,
  `num_ordem` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_emenda` int DEFAULT NULL,
  `cod_substitutivo` int DEFAULT NULL,
  `cod_parecer` int DEFAULT NULL,
  `cod_relator` int DEFAULT NULL,
  `tip_resultado_votacao` int UNSIGNED DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `reuniao_comissao_presenca`
--

CREATE TABLE `reuniao_comissao_presenca` (
  `id` int NOT NULL,
  `cod_reuniao` int NOT NULL,
  `cod_parlamentar` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `sessao_legislativa`
--

CREATE TABLE `sessao_legislativa` (
  `cod_sessao_leg` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `num_sessao_leg` tinyint NOT NULL,
  `tip_sessao_leg` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_inicio` date NOT NULL,
  `dat_fim` date NOT NULL,
  `dat_inicio_intervalo` date DEFAULT NULL,
  `dat_fim_intervalo` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `sessao_plenaria`
--

CREATE TABLE `sessao_plenaria` (
  `cod_sessao_plen` int NOT NULL,
  `cod_andamento_sessao` int DEFAULT NULL,
  `tip_sessao` tinyint NOT NULL,
  `cod_periodo_sessao` int DEFAULT NULL,
  `cod_sessao_leg` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `tip_expediente` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_inicio_sessao` date NOT NULL,
  `dia_sessao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hr_inicio_sessao` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hr_fim_sessao` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_sessao_plen` int UNSIGNED NOT NULL,
  `dat_fim_sessao` date DEFAULT NULL,
  `url_fotos` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `url_audio` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `url_video` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sepl_termo_encerramento` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `sepl_consideracoes` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `sepl_local_sessao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `numero_ata` int DEFAULT NULL,
  `ano_ata` int DEFAULT NULL,
  `votacao_requerimento_ata` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `votacao_mocao_ata` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `votacao_ordem_dia_ata` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `sessao_plenaria_painel`
--

CREATE TABLE `sessao_plenaria_painel` (
  `cod_item` int NOT NULL,
  `tip_item` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `nom_fase` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_ordem` int NOT NULL,
  `txt_exibicao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `txt_autoria` varchar(400) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_turno` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_inicio` datetime DEFAULT NULL,
  `dat_fim` datetime DEFAULT NULL,
  `ind_extrapauta` tinyint DEFAULT '0',
  `ind_exibicao` tinyint DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `sessao_plenaria_presenca`
--

CREATE TABLE `sessao_plenaria_presenca` (
  `cod_presenca_sessao` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `tip_frequencia` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'P',
  `txt_justif_ausencia` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_sessao` date DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `status_tramitacao`
--

CREATE TABLE `status_tramitacao` (
  `cod_status` int NOT NULL,
  `sgl_status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_status` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_fim_tramitacao` tinyint NOT NULL DEFAULT '0',
  `ind_retorno_tramitacao` tinyint NOT NULL DEFAULT '0',
  `num_dias_prazo` tinyint DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `status_tramitacao_administrativo`
--

CREATE TABLE `status_tramitacao_administrativo` (
  `cod_status` int NOT NULL,
  `sgl_status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_status` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_fim_tramitacao` tinyint NOT NULL DEFAULT '0',
  `ind_retorno_tramitacao` tinyint NOT NULL DEFAULT '0',
  `num_dias_prazo` tinyint DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `subemenda`
--

CREATE TABLE `subemenda` (
  `cod_subemenda` int NOT NULL,
  `tip_subemenda` int NOT NULL,
  `num_subemenda` int NOT NULL,
  `cod_emenda` int NOT NULL,
  `num_protocolo` int DEFAULT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `txt_ementa` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_autor` int NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `substitutivo`
--

CREATE TABLE `substitutivo` (
  `cod_substitutivo` int NOT NULL,
  `num_substitutivo` int NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_autor` int DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_afastamento`
--

CREATE TABLE `tipo_afastamento` (
  `tip_afastamento` int NOT NULL,
  `des_afastamento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_afastamento` int NOT NULL,
  `ind_fim_mandato` int NOT NULL,
  `des_dispositivo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_autor`
--

CREATE TABLE `tipo_autor` (
  `tip_autor` tinyint NOT NULL,
  `des_tipo_autor` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_proposicao` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_comissao`
--

CREATE TABLE `tipo_comissao` (
  `tip_comissao` int NOT NULL,
  `nom_tipo_comissao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_natureza_comissao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_tipo_comissao` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_dispositivo_regimental` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_dependente`
--

CREATE TABLE `tipo_dependente` (
  `tip_dependente` tinyint NOT NULL,
  `des_tipo_dependente` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_documento`
--

CREATE TABLE `tipo_documento` (
  `tip_documento` int NOT NULL,
  `des_tipo_documento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_documento_administrativo`
--

CREATE TABLE `tipo_documento_administrativo` (
  `tip_documento` int NOT NULL,
  `sgl_tipo_documento` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tipo_documento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_publico` tinyint NOT NULL DEFAULT '0',
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_emenda`
--

CREATE TABLE `tipo_emenda` (
  `tip_emenda` int NOT NULL,
  `des_tipo_emenda` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_expediente`
--

CREATE TABLE `tipo_expediente` (
  `cod_expediente` int NOT NULL,
  `nom_expediente` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ordem` int DEFAULT NULL,
  `ind_excluido` tinyint UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_fim_relatoria`
--

CREATE TABLE `tipo_fim_relatoria` (
  `tip_fim_relatoria` tinyint NOT NULL,
  `des_fim_relatoria` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_instituicao`
--

CREATE TABLE `tipo_instituicao` (
  `tip_instituicao` int NOT NULL,
  `nom_tipo_instituicao` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_materia_legislativa`
--

CREATE TABLE `tipo_materia_legislativa` (
  `tip_materia` int NOT NULL,
  `sgl_tipo_materia` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tipo_materia` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_natureza` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_publico` tinyint NOT NULL DEFAULT '1',
  `ind_num_automatica` tinyint NOT NULL DEFAULT '0',
  `quorum_minimo_votacao` tinyint NOT NULL DEFAULT '1',
  `ordem` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_norma_juridica`
--

CREATE TABLE `tipo_norma_juridica` (
  `tip_norma` tinyint NOT NULL,
  `voc_lexml` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_tipo_norma` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tipo_norma` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_peticionamento`
--

CREATE TABLE `tipo_peticionamento` (
  `tip_peticionamento` int NOT NULL,
  `des_tipo_peticionamento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_norma` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_doc_adm` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_doc_materia` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_derivado` int NOT NULL,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_proposicao`
--

CREATE TABLE `tipo_proposicao` (
  `tip_proposicao` int NOT NULL,
  `des_tipo_proposicao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_mat_ou_doc` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_mat_ou_doc` int NOT NULL,
  `nom_modelo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_resultado_votacao`
--

CREATE TABLE `tipo_resultado_votacao` (
  `tip_resultado_votacao` int UNSIGNED NOT NULL,
  `nom_resultado` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint UNSIGNED NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_sessao_plenaria`
--

CREATE TABLE `tipo_sessao_plenaria` (
  `tip_sessao` tinyint NOT NULL,
  `nom_sessao` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL,
  `num_minimo` int NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_situacao_materia`
--

CREATE TABLE `tipo_situacao_materia` (
  `tip_situacao_materia` int NOT NULL,
  `des_tipo_situacao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_situacao_militar`
--

CREATE TABLE `tipo_situacao_militar` (
  `tip_situacao_militar` tinyint NOT NULL,
  `des_tipo_situacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_situacao_norma`
--

CREATE TABLE `tipo_situacao_norma` (
  `tip_situacao_norma` int NOT NULL,
  `des_tipo_situacao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_vinculo_norma`
--

CREATE TABLE `tipo_vinculo_norma` (
  `cod_tip_vinculo` int NOT NULL,
  `tipo_vinculo` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_vinculo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_vinculo_passivo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tip_situacao` int DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tipo_votacao`
--

CREATE TABLE `tipo_votacao` (
  `tip_votacao` int NOT NULL,
  `des_tipo_votacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tramitacao`
--

CREATE TABLE `tramitacao` (
  `cod_tramitacao` int NOT NULL,
  `cod_status` int DEFAULT NULL,
  `cod_materia` int NOT NULL,
  `dat_tramitacao` datetime DEFAULT NULL,
  `cod_unid_tram_local` int DEFAULT NULL,
  `cod_usuario_local` int DEFAULT NULL,
  `dat_encaminha` datetime DEFAULT NULL,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `cod_usuario_dest` int DEFAULT NULL,
  `dat_recebimento` datetime DEFAULT NULL,
  `ind_ult_tramitacao` int NOT NULL,
  `ind_urgencia` int NOT NULL,
  `sgl_turno` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_tramitacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_fim_prazo` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `tramitacao_administrativo`
--

CREATE TABLE `tramitacao_administrativo` (
  `cod_tramitacao` int NOT NULL,
  `cod_documento` int NOT NULL DEFAULT '0',
  `dat_tramitacao` datetime DEFAULT NULL,
  `cod_unid_tram_local` int DEFAULT NULL,
  `cod_usuario_local` int DEFAULT NULL,
  `dat_encaminha` datetime DEFAULT NULL,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `cod_usuario_dest` int DEFAULT NULL,
  `dat_recebimento` datetime DEFAULT NULL,
  `cod_status` int DEFAULT NULL,
  `ind_ult_tramitacao` tinyint NOT NULL DEFAULT '0',
  `txt_tramitacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_fim_prazo` date DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

-- --------------------------------------------------------

--
-- Estrutura para tabela `turno_discussao`
--

CREATE TABLE `turno_discussao` (
  `cod_turno` int NOT NULL,
  `sgl_turno` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'S',
  `des_turno` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `unidade_tramitacao`
--

CREATE TABLE `unidade_tramitacao` (
  `cod_unid_tramitacao` int NOT NULL,
  `cod_comissao` int DEFAULT NULL,
  `cod_orgao` int DEFAULT NULL,
  `cod_parlamentar` int DEFAULT NULL,
  `ind_leg` tinyint DEFAULT '0',
  `unid_dest_permitidas` varchar(400) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status_permitidos` varchar(400) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_adm` tinyint DEFAULT '0',
  `status_adm_permitidos` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `usuario`
--

CREATE TABLE `usuario` (
  `cod_usuario` int NOT NULL,
  `col_username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_interno` int NOT NULL DEFAULT '1',
  `nom_completo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `des_estado_civil` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sex_usuario` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_cpf` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `num_rg` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_ctps` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_serie_ctps` varchar(4) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_pis_pasep` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_residencial` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_localidade_resid` int DEFAULT NULL,
  `num_cep_resid` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_resid` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_celular` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `num_matricula` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_lotacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_vinculo` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_comercial` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_ramal` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_ativo` int NOT NULL DEFAULT '1',
  `ind_excluido` tinyint NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `usuario_peticionamento`
--

CREATE TABLE `usuario_peticionamento` (
  `id` int NOT NULL,
  `cod_usuario` int NOT NULL,
  `tip_peticionamento` int NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `usuario_tipo_documento`
--

CREATE TABLE `usuario_tipo_documento` (
  `id` int NOT NULL,
  `cod_usuario` int NOT NULL,
  `tip_documento` int NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `usuario_unid_tram`
--

CREATE TABLE `usuario_unid_tram` (
  `id` int NOT NULL,
  `cod_usuario` int NOT NULL,
  `cod_unid_tramitacao` int NOT NULL,
  `ind_responsavel` tinyint NOT NULL DEFAULT '0',
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `vinculo_norma_juridica`
--

CREATE TABLE `vinculo_norma_juridica` (
  `cod_vinculo` int NOT NULL,
  `cod_norma_referente` int NOT NULL,
  `cod_norma_referida` int DEFAULT NULL,
  `tip_vinculo` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao_vinculo` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

-- --------------------------------------------------------

--
-- Estrutura para tabela `visita`
--

CREATE TABLE `visita` (
  `cod_visita` int NOT NULL,
  `cod_pessoa` int NOT NULL,
  `dat_entrada` datetime NOT NULL,
  `cod_funcionario` int NOT NULL,
  `num_cracha` int DEFAULT NULL,
  `dat_saida` datetime DEFAULT NULL,
  `txt_atendimento` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `des_situacao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_solucao` date DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` tinyint NOT NULL DEFAULT '0'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Índices para tabelas despejadas
--

--
-- Índices de tabela `acomp_materia`
--
ALTER TABLE `acomp_materia`
  ADD PRIMARY KEY (`cod_cadastro`),
  ADD UNIQUE KEY `fk_{CCECA63D-5992-437B-BCD3-D7C98DA3E926}` (`cod_materia`,`end_email`),
  ADD KEY `cod_materia` (`cod_materia`);

--
-- Índices de tabela `afastamento`
--
ALTER TABLE `afastamento`
  ADD PRIMARY KEY (`cod_afastamento`),
  ADD KEY `idx_parlamentar_mandato` (`cod_parlamentar`,`num_legislatura`),
  ADD KEY `idx_afastamento_datas` (`cod_parlamentar`,`dat_inicio_afastamento`,`dat_fim_afastamento`),
  ADD KEY `idx_tip_afastamento` (`tip_afastamento`),
  ADD KEY `idx__parlamentar_suplente` (`cod_parlamentar_suplente`,`num_legislatura`),
  ADD KEY `cod_mandato` (`cod_mandato`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `num_legislatura` (`num_legislatura`),
  ADD KEY `cod_parlamentar_suplente` (`cod_parlamentar_suplente`);

--
-- Índices de tabela `anexada`
--
ALTER TABLE `anexada`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_materia_anexada` (`cod_materia_anexada`),
  ADD KEY `idx_materia_principal` (`cod_materia_principal`);

--
-- Índices de tabela `anexo_norma`
--
ALTER TABLE `anexo_norma`
  ADD PRIMARY KEY (`cod_anexo`),
  ADD KEY `cod_norma` (`cod_norma`);

--
-- Índices de tabela `arquivo_armario`
--
ALTER TABLE `arquivo_armario`
  ADD PRIMARY KEY (`cod_armario`),
  ADD KEY `cod_corredor` (`cod_corredor`),
  ADD KEY `cod_unidade` (`cod_unidade`);

--
-- Índices de tabela `arquivo_corredor`
--
ALTER TABLE `arquivo_corredor`
  ADD PRIMARY KEY (`cod_corredor`),
  ADD KEY `cod_unidade` (`cod_unidade`);

--
-- Índices de tabela `arquivo_item`
--
ALTER TABLE `arquivo_item`
  ADD PRIMARY KEY (`cod_item`),
  ADD KEY `cod_recipiente` (`cod_recipiente`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_norma` (`cod_norma`),
  ADD KEY `cod_documento` (`cod_documento`),
  ADD KEY `cod_protocolo` (`cod_protocolo`),
  ADD KEY `tip_suporte` (`tip_suporte`);

--
-- Índices de tabela `arquivo_prateleira`
--
ALTER TABLE `arquivo_prateleira`
  ADD PRIMARY KEY (`cod_prateleira`),
  ADD KEY `cod_armario` (`cod_armario`),
  ADD KEY `cod_corredor` (`cod_corredor`),
  ADD KEY `cod_unidade` (`cod_unidade`);

--
-- Índices de tabela `arquivo_recipiente`
--
ALTER TABLE `arquivo_recipiente`
  ADD PRIMARY KEY (`cod_recipiente`),
  ADD UNIQUE KEY `num_tipo_recipiente` (`num_recipiente`,`tip_recipiente`,`ano_recipiente`,`ind_excluido`),
  ADD KEY `tip_recipiente` (`tip_recipiente`),
  ADD KEY `tip_tit_documental` (`tip_tit_documental`);

--
-- Índices de tabela `arquivo_tipo_recipiente`
--
ALTER TABLE `arquivo_tipo_recipiente`
  ADD PRIMARY KEY (`tip_recipiente`);

--
-- Índices de tabela `arquivo_tipo_suporte`
--
ALTER TABLE `arquivo_tipo_suporte`
  ADD PRIMARY KEY (`tip_suporte`);

--
-- Índices de tabela `arquivo_tipo_tit_documental`
--
ALTER TABLE `arquivo_tipo_tit_documental`
  ADD PRIMARY KEY (`tip_tit_documental`);

--
-- Índices de tabela `arquivo_unidade`
--
ALTER TABLE `arquivo_unidade`
  ADD PRIMARY KEY (`cod_unidade`);

--
-- Índices de tabela `assessor_parlamentar`
--
ALTER TABLE `assessor_parlamentar`
  ADD PRIMARY KEY (`cod_assessor`),
  ADD UNIQUE KEY `assessor_parlamentar` (`cod_assessor`,`cod_parlamentar`,`ind_excluido`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`);

--
-- Índices de tabela `assinatura_documento`
--
ALTER TABLE `assinatura_documento`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_cod_assinatura_doc` (`cod_assinatura_doc`,`codigo`,`tipo_doc`,`cod_usuario`) USING BTREE,
  ADD KEY `ind_assinado` (`ind_assinado`),
  ADD KEY `ind_recusado` (`ind_recusado`),
  ADD KEY `assinatura_documento_ibfk` (`cod_usuario`) USING BTREE,
  ADD KEY `tipo_doc` (`tipo_doc`);

--
-- Índices de tabela `assinatura_storage`
--
ALTER TABLE `assinatura_storage`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tip_documento` (`tip_documento`);

--
-- Índices de tabela `assunto_materia`
--
ALTER TABLE `assunto_materia`
  ADD PRIMARY KEY (`cod_assunto`);

--
-- Índices de tabela `assunto_norma`
--
ALTER TABLE `assunto_norma`
  ADD PRIMARY KEY (`cod_assunto`);

--
-- Índices de tabela `assunto_proposicao`
--
ALTER TABLE `assunto_proposicao`
  ADD PRIMARY KEY (`cod_assunto`),
  ADD KEY `tip_proposicao` (`tip_proposicao`),
  ADD KEY `des_assunto` (`des_assunto`);

--
-- Índices de tabela `autor`
--
ALTER TABLE `autor`
  ADD PRIMARY KEY (`cod_autor`),
  ADD KEY `idx_tip_autor` (`tip_autor`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`),
  ADD KEY `idx_comissao` (`cod_comissao`),
  ADD KEY `idx_partido` (`cod_partido`),
  ADD KEY `idx_bancada` (`cod_bancada`);
ALTER TABLE `autor` ADD FULLTEXT KEY `nom_autor` (`nom_autor`);

--
-- Índices de tabela `autoria`
--
ALTER TABLE `autoria`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_materia` (`cod_materia`),
  ADD KEY `idx_autor` (`cod_autor`);

--
-- Índices de tabela `autoria_emenda`
--
ALTER TABLE `autoria_emenda`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_autor` (`cod_autor`),
  ADD KEY `idx_emenda` (`cod_emenda`) USING BTREE;

--
-- Índices de tabela `autoria_substitutivo`
--
ALTER TABLE `autoria_substitutivo`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_autor` (`cod_autor`),
  ADD KEY `idx_substitutivo` (`cod_substitutivo`) USING BTREE;

--
-- Índices de tabela `bancada`
--
ALTER TABLE `bancada`
  ADD PRIMARY KEY (`cod_bancada`),
  ADD KEY `idt_nom_bancada` (`nom_bancada`),
  ADD KEY `num_legislatura` (`num_legislatura`),
  ADD KEY `cod_partido` (`cod_partido`);
ALTER TABLE `bancada` ADD FULLTEXT KEY `nom_bancada` (`nom_bancada`);

--
-- Índices de tabela `cargo_bancada`
--
ALTER TABLE `cargo_bancada`
  ADD PRIMARY KEY (`cod_cargo`);

--
-- Índices de tabela `cargo_comissao`
--
ALTER TABLE `cargo_comissao`
  ADD PRIMARY KEY (`cod_cargo`);

--
-- Índices de tabela `cargo_executivo`
--
ALTER TABLE `cargo_executivo`
  ADD PRIMARY KEY (`cod_cargo`);

--
-- Índices de tabela `cargo_mesa`
--
ALTER TABLE `cargo_mesa`
  ADD PRIMARY KEY (`cod_cargo`);

--
-- Índices de tabela `categoria_instituicao`
--
ALTER TABLE `categoria_instituicao`
  ADD PRIMARY KEY (`cod_categoria`,`tip_instituicao`) USING BTREE,
  ADD KEY `tip_instituicao` (`tip_instituicao`) USING BTREE;

--
-- Índices de tabela `coautoria_proposicao`
--
ALTER TABLE `coautoria_proposicao`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_proposicao` (`cod_proposicao`),
  ADD KEY `idx_autor` (`cod_autor`);

--
-- Índices de tabela `coligacao`
--
ALTER TABLE `coligacao`
  ADD PRIMARY KEY (`cod_coligacao`),
  ADD KEY `idx_legislatura` (`num_legislatura`),
  ADD KEY `idx_coligacao_legislatura` (`num_legislatura`,`ind_excluido`);

--
-- Índices de tabela `comissao`
--
ALTER TABLE `comissao`
  ADD PRIMARY KEY (`cod_comissao`),
  ADD KEY `idx_comissao_tipo` (`tip_comissao`),
  ADD KEY `idx_comissao_nome` (`nom_comissao`);
ALTER TABLE `comissao` ADD FULLTEXT KEY `nom_comissao` (`nom_comissao`);

--
-- Índices de tabela `composicao_bancada`
--
ALTER TABLE `composicao_bancada`
  ADD PRIMARY KEY (`cod_comp_bancada`),
  ADD KEY `idx_cargo` (`cod_cargo`),
  ADD KEY `idx_bancada` (`cod_bancada`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_periodo_comp` (`cod_periodo_comp`);

--
-- Índices de tabela `composicao_coligacao`
--
ALTER TABLE `composicao_coligacao`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_coligacao` (`cod_coligacao`),
  ADD KEY `idx_partido` (`cod_partido`);

--
-- Índices de tabela `composicao_comissao`
--
ALTER TABLE `composicao_comissao`
  ADD PRIMARY KEY (`cod_comp_comissao`),
  ADD KEY `idx_cargo` (`cod_cargo`),
  ADD KEY `idx_periodo_comp` (`cod_periodo_comp`),
  ADD KEY `idx_comissao` (`cod_comissao`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`);

--
-- Índices de tabela `composicao_executivo`
--
ALTER TABLE `composicao_executivo`
  ADD PRIMARY KEY (`cod_composicao`),
  ADD KEY `num_legislatura` (`num_legislatura`),
  ADD KEY `cod_cargo` (`cod_cargo`),
  ADD KEY `cod_partido` (`cod_partido`);

--
-- Índices de tabela `composicao_mesa`
--
ALTER TABLE `composicao_mesa`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_cargo` (`cod_cargo`),
  ADD KEY `idx_periodo_comp` (`cod_periodo_comp`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_sessao_leg` (`cod_sessao_leg`);

--
-- Índices de tabela `dependente`
--
ALTER TABLE `dependente`
  ADD PRIMARY KEY (`cod_dependente`),
  ADD KEY `idx_dep_parlam` (`tip_dependente`,`cod_parlamentar`,`ind_excluido`),
  ADD KEY `idx_dependente` (`tip_dependente`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`);

--
-- Índices de tabela `despacho_inicial`
--
ALTER TABLE `despacho_inicial`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_unique` (`cod_materia`,`num_ordem`),
  ADD KEY `idx_comissao` (`cod_comissao`),
  ADD KEY `idx_materia` (`cod_materia`),
  ADD KEY `idx_despinic_comissao` (`cod_materia`,`num_ordem`,`cod_comissao`);

--
-- Índices de tabela `destinatario_oficio`
--
ALTER TABLE `destinatario_oficio`
  ADD PRIMARY KEY (`cod_destinatario`),
  ADD KEY `cod_documento` (`cod_documento`),
  ADD KEY `cod_instituicao` (`cod_instituicao`);

--
-- Índices de tabela `documento_acessorio`
--
ALTER TABLE `documento_acessorio`
  ADD PRIMARY KEY (`cod_documento`),
  ADD KEY `idx_tip_documento` (`tip_documento`),
  ADD KEY `idx_materia` (`cod_materia`),
  ADD KEY `ind_publico` (`ind_publico`);
ALTER TABLE `documento_acessorio` ADD FULLTEXT KEY `idx_ementa` (`txt_ementa`);

--
-- Índices de tabela `documento_acessorio_administrativo`
--
ALTER TABLE `documento_acessorio_administrativo`
  ADD PRIMARY KEY (`cod_documento_acessorio`),
  ADD KEY `idx_tip_documento` (`tip_documento`),
  ADD KEY `idx_documento` (`cod_documento`),
  ADD KEY `idx_autor_documento` (`nom_autor_documento`),
  ADD KEY `idx_dat_documento` (`dat_documento`);
ALTER TABLE `documento_acessorio_administrativo` ADD FULLTEXT KEY `idx_assunto` (`txt_assunto`);

--
-- Índices de tabela `documento_administrativo`
--
ALTER TABLE `documento_administrativo`
  ADD PRIMARY KEY (`cod_documento`),
  ADD KEY `tip_documento` (`tip_documento`,`num_documento`,`ano_documento`),
  ADD KEY `cod_situacao` (`cod_situacao`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_entidade` (`cod_entidade`),
  ADD KEY `cod_autor` (`cod_autor`),
  ADD KEY `ano_documento` (`ano_documento`),
  ADD KEY `dat_documento` (`dat_documento`),
  ADD KEY `num_protocolo` (`num_protocolo`);
ALTER TABLE `documento_administrativo` ADD FULLTEXT KEY `idx_busca_documento` (`txt_assunto`,`txt_observacao`);
ALTER TABLE `documento_administrativo` ADD FULLTEXT KEY `txt_interessado` (`txt_interessado`);

--
-- Índices de tabela `documento_administrativo_materia`
--
ALTER TABLE `documento_administrativo_materia`
  ADD PRIMARY KEY (`cod_vinculo`),
  ADD KEY `idx_cod_documento` (`cod_documento`),
  ADD KEY `idx_cod_materia` (`cod_materia`);

--
-- Índices de tabela `documento_administrativo_vinculado`
--
ALTER TABLE `documento_administrativo_vinculado`
  ADD PRIMARY KEY (`cod_vinculo`),
  ADD UNIQUE KEY `idx_doc_vinculo` (`cod_documento_vinculante`,`cod_documento_vinculado`),
  ADD KEY `idx_doc_vinculado` (`cod_documento_vinculado`) USING BTREE,
  ADD KEY `idx_cod_documento` (`cod_documento_vinculante`) USING BTREE;

--
-- Índices de tabela `documento_comissao`
--
ALTER TABLE `documento_comissao`
  ADD PRIMARY KEY (`cod_documento`),
  ADD KEY `cod_comissao` (`cod_comissao`);
ALTER TABLE `documento_comissao` ADD FULLTEXT KEY `txt_descricao` (`txt_descricao`);

--
-- Índices de tabela `emenda`
--
ALTER TABLE `emenda`
  ADD PRIMARY KEY (`cod_emenda`),
  ADD KEY `idx_cod_materia` (`cod_materia`),
  ADD KEY `idx_tip_emenda` (`tip_emenda`),
  ADD KEY `idx_emenda` (`cod_emenda`,`tip_emenda`,`cod_materia`) USING BTREE,
  ADD KEY `cod_autor` (`cod_autor`);
ALTER TABLE `emenda` ADD FULLTEXT KEY `idx_txt_ementa` (`txt_ementa`);

--
-- Índices de tabela `encerramento_presenca`
--
ALTER TABLE `encerramento_presenca`
  ADD PRIMARY KEY (`cod_presenca_encerramento`),
  ADD UNIQUE KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `dat_ordem` (`dat_ordem`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`);

--
-- Índices de tabela `expediente_discussao`
--
ALTER TABLE `expediente_discussao`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cod_ordem` (`cod_ordem`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`);

--
-- Índices de tabela `expediente_materia`
--
ALTER TABLE `expediente_materia`
  ADD PRIMARY KEY (`cod_ordem`),
  ADD KEY `idx_exped_datord` (`dat_ordem`,`ind_excluido`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `tip_votacao` (`tip_votacao`),
  ADD KEY `tip_quorum` (`tip_quorum`),
  ADD KEY `cod_parecer` (`cod_parecer`),
  ADD KEY `tip_turno` (`tip_turno`);

--
-- Índices de tabela `expediente_presenca`
--
ALTER TABLE `expediente_presenca`
  ADD PRIMARY KEY (`cod_presenca_expediente`),
  ADD UNIQUE KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `dat_ordem` (`dat_ordem`,`ind_excluido`);

--
-- Índices de tabela `expediente_sessao_plenaria`
--
ALTER TABLE `expediente_sessao_plenaria`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `cod_expediente` (`cod_expediente`);

--
-- Índices de tabela `filiacao`
--
ALTER TABLE `filiacao`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_partido` (`cod_partido`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`),
  ADD KEY `dat_filiacao` (`dat_filiacao`),
  ADD KEY `dat_desfiliacao` (`dat_desfiliacao`);

--
-- Índices de tabela `funcionario`
--
ALTER TABLE `funcionario`
  ADD PRIMARY KEY (`cod_funcionario`),
  ADD KEY `cod_usuario` (`cod_usuario`);

--
-- Índices de tabela `gabinete_atendimento`
--
ALTER TABLE `gabinete_atendimento`
  ADD PRIMARY KEY (`cod_atendimento`),
  ADD KEY `idx_resultado` (`txt_resultado`) USING BTREE,
  ADD KEY `idx_eleitor` (`cod_eleitor`) USING BTREE,
  ADD KEY `idx_parlamentar` (`cod_parlamentar`) USING BTREE;
ALTER TABLE `gabinete_atendimento` ADD FULLTEXT KEY `idx_assunto` (`txt_assunto`);

--
-- Índices de tabela `gabinete_eleitor`
--
ALTER TABLE `gabinete_eleitor`
  ADD PRIMARY KEY (`cod_eleitor`),
  ADD KEY `sex_eleitor` (`sex_eleitor`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_assessor` (`cod_assessor`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `nom_eleitor` (`nom_eleitor`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `des_profissao` (`des_profissao`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `end_residencial` (`end_residencial`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `nom_localidade` (`nom_localidade`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `des_local_trabalho` (`des_local_trabalho`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `nom_bairro` (`nom_bairro`);

--
-- Índices de tabela `instituicao`
--
ALTER TABLE `instituicao`
  ADD PRIMARY KEY (`cod_instituicao`),
  ADD KEY `tip_instituicao` (`tip_instituicao`),
  ADD KEY `cod_categoria` (`cod_categoria`),
  ADD KEY `cod_localidade` (`cod_localidade`),
  ADD KEY `ind_excluido` (`ind_excluido`),
  ADD KEY `idx_cod_cat` (`tip_instituicao`,`cod_categoria`);
ALTER TABLE `instituicao` ADD FULLTEXT KEY `idx_nom_instituicao` (`nom_instituicao`);
ALTER TABLE `instituicao` ADD FULLTEXT KEY `idx_nom_responsavel` (`nom_responsavel`);

--
-- Índices de tabela `legislacao_citada`
--
ALTER TABLE `legislacao_citada`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cod_norma` (`cod_norma`),
  ADD KEY `cod_materia` (`cod_materia`);

--
-- Índices de tabela `legislatura`
--
ALTER TABLE `legislatura`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `num_legislatura` (`num_legislatura`),
  ADD KEY `idx_legislatura_datas` (`dat_inicio`,`dat_fim`,`dat_eleicao`,`ind_excluido`),
  ADD KEY `num_legislatura_2` (`num_legislatura`);

--
-- Índices de tabela `lexml_registro_provedor`
--
ALTER TABLE `lexml_registro_provedor`
  ADD PRIMARY KEY (`cod_provedor`);

--
-- Índices de tabela `lexml_registro_publicador`
--
ALTER TABLE `lexml_registro_publicador`
  ADD PRIMARY KEY (`cod_publicador`);

--
-- Índices de tabela `liderancas_partidarias`
--
ALTER TABLE `liderancas_partidarias`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_num_ordem` (`cod_sessao_plen`,`num_ordem`,`ind_excluido`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `cod_partido` (`cod_partido`);

--
-- Índices de tabela `localidade`
--
ALTER TABLE `localidade`
  ADD PRIMARY KEY (`cod_localidade`),
  ADD KEY `nom_localidade` (`nom_localidade`),
  ADD KEY `sgl_uf` (`sgl_uf`),
  ADD KEY `tip_localidade` (`tip_localidade`);
ALTER TABLE `localidade` ADD FULLTEXT KEY `nom_localidade_pesq` (`nom_localidade_pesq`);

--
-- Índices de tabela `logradouro`
--
ALTER TABLE `logradouro`
  ADD PRIMARY KEY (`cod_logradouro`),
  ADD KEY `num_cep` (`num_cep`),
  ADD KEY `cod_localidade` (`cod_localidade`),
  ADD KEY `logradouro_ibfk_2` (`cod_norma`);
ALTER TABLE `logradouro` ADD FULLTEXT KEY `nom_logradouro` (`nom_logradouro`);

--
-- Índices de tabela `mandato`
--
ALTER TABLE `mandato`
  ADD PRIMARY KEY (`cod_mandato`),
  ADD KEY `idx_coligacao` (`cod_coligacao`),
  ADD KEY `idx_parlamentar` (`cod_parlamentar`),
  ADD KEY `idx_afastamento` (`tip_afastamento`),
  ADD KEY `idx_mandato_legislatura` (`num_legislatura`,`cod_parlamentar`,`ind_excluido`),
  ADD KEY `idx_legislatura` (`num_legislatura`),
  ADD KEY `tip_causa_fim_mandato` (`tip_causa_fim_mandato`);

--
-- Índices de tabela `materia_apresentada_sessao`
--
ALTER TABLE `materia_apresentada_sessao`
  ADD PRIMARY KEY (`cod_ordem`),
  ADD KEY `fk_cod_materia` (`cod_materia`),
  ADD KEY `idx_apres_datord` (`dat_ordem`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `idx_cod_documento` (`cod_documento`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_materia_2` (`cod_materia`),
  ADD KEY `cod_emenda` (`cod_emenda`),
  ADD KEY `cod_substitutivo` (`cod_substitutivo`),
  ADD KEY `cod_doc_acessorio` (`cod_doc_acessorio`),
  ADD KEY `cod_parecer` (`cod_parecer`);

--
-- Índices de tabela `materia_legislativa`
--
ALTER TABLE `materia_legislativa`
  ADD PRIMARY KEY (`cod_materia`),
  ADD KEY `cod_local_origem_externa` (`cod_local_origem_externa`),
  ADD KEY `tip_origem_externa` (`tip_origem_externa`),
  ADD KEY `cod_regime_tramitacao` (`cod_regime_tramitacao`),
  ADD KEY `idx_dat_apresentacao` (`dat_apresentacao`,`tip_id_basica`,`ind_excluido`),
  ADD KEY `idx_matleg_dat_publicacao` (`dat_publicacao`,`tip_id_basica`,`ind_excluido`),
  ADD KEY `cod_situacao` (`cod_situacao`),
  ADD KEY `idx_mat_principal` (`cod_materia_principal`),
  ADD KEY `tip_quorum` (`tip_quorum`),
  ADD KEY `tip_id_basica` (`tip_id_basica`) USING BTREE,
  ADD KEY `idx_matleg_ident` (`ind_excluido`,`tip_id_basica`,`ano_ident_basica`,`num_ident_basica`) USING BTREE,
  ADD KEY `idx_tramitacao` (`ind_tramitacao`) USING BTREE,
  ADD KEY `idx_assunto` (`cod_assunto`);
ALTER TABLE `materia_legislativa` ADD FULLTEXT KEY `idx_busca` (`txt_ementa`,`txt_observacao`,`txt_indexacao`);

--
-- Índices de tabela `mesa_sessao_plenaria`
--
ALTER TABLE `mesa_sessao_plenaria`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cod_sessao_leg` (`cod_sessao_leg`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_cargo` (`cod_cargo`);

--
-- Índices de tabela `nivel_instrucao`
--
ALTER TABLE `nivel_instrucao`
  ADD PRIMARY KEY (`cod_nivel_instrucao`);

--
-- Índices de tabela `norma_juridica`
--
ALTER TABLE `norma_juridica`
  ADD PRIMARY KEY (`cod_norma`),
  ADD KEY `cod_assunto` (`cod_assunto`),
  ADD KEY `tip_norma` (`tip_norma`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `idx_ano_numero` (`ano_norma`,`num_norma`,`ind_excluido`),
  ADD KEY `dat_norma` (`dat_norma`),
  ADD KEY `cod_situacao` (`cod_situacao`),
  ADD KEY `ind_publico` (`ind_publico`);
ALTER TABLE `norma_juridica` ADD FULLTEXT KEY `idx_busca` (`txt_ementa`,`txt_observacao`,`txt_indexacao`);

--
-- Índices de tabela `numeracao`
--
ALTER TABLE `numeracao`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `tip_materia` (`tip_materia`),
  ADD KEY `idx_numer_identificacao` (`tip_materia`,`num_materia`,`ano_materia`,`ind_excluido`);

--
-- Índices de tabela `oradores`
--
ALTER TABLE `oradores`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_num_ordem` (`cod_sessao_plen`,`num_ordem`,`ind_excluido`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`);

--
-- Índices de tabela `oradores_expediente`
--
ALTER TABLE `oradores_expediente`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_num_ordem` (`cod_sessao_plen`,`num_ordem`,`ind_excluido`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`);

--
-- Índices de tabela `ordem_dia`
--
ALTER TABLE `ordem_dia`
  ADD PRIMARY KEY (`cod_ordem`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `idx_dat_ordem` (`dat_ordem`),
  ADD KEY `tip_votacao` (`tip_votacao`),
  ADD KEY `tip_quorum` (`tip_quorum`),
  ADD KEY `tip_turno` (`tip_turno`),
  ADD KEY `num_ordem` (`num_ordem`),
  ADD KEY `idx_cod_parecer` (`cod_parecer`);

--
-- Índices de tabela `ordem_dia_discussao`
--
ALTER TABLE `ordem_dia_discussao`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cod_ordem` (`cod_ordem`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`);

--
-- Índices de tabela `ordem_dia_presenca`
--
ALTER TABLE `ordem_dia_presenca`
  ADD PRIMARY KEY (`cod_presenca_ordem_dia`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `dat_ordem` (`dat_ordem`),
  ADD KEY `tip_frequencia` (`tip_frequencia`);

--
-- Índices de tabela `orgao`
--
ALTER TABLE `orgao`
  ADD PRIMARY KEY (`cod_orgao`);

--
-- Índices de tabela `origem`
--
ALTER TABLE `origem`
  ADD PRIMARY KEY (`cod_origem`);

--
-- Índices de tabela `parecer`
--
ALTER TABLE `parecer`
  ADD PRIMARY KEY (`cod_relatoria`,`cod_materia`),
  ADD KEY `idx_parecer_materia` (`cod_materia`,`ind_excluido`),
  ADD KEY `cod_materia` (`cod_materia`);

--
-- Índices de tabela `parlamentar`
--
ALTER TABLE `parlamentar`
  ADD PRIMARY KEY (`cod_parlamentar`),
  ADD KEY `cod_localidade_resid` (`cod_localidade_resid`),
  ADD KEY `tip_situacao_militar` (`tip_situacao_militar`),
  ADD KEY `cod_nivel_instrucao` (`cod_nivel_instrucao`),
  ADD KEY `ind_parlamentar_ativo` (`ind_ativo`,`ind_excluido`);
ALTER TABLE `parlamentar` ADD FULLTEXT KEY `nom_completo` (`nom_completo`);
ALTER TABLE `parlamentar` ADD FULLTEXT KEY `nom_parlamentar` (`nom_parlamentar`);

--
-- Índices de tabela `partido`
--
ALTER TABLE `partido`
  ADD PRIMARY KEY (`cod_partido`);

--
-- Índices de tabela `periodo_comp_bancada`
--
ALTER TABLE `periodo_comp_bancada`
  ADD PRIMARY KEY (`cod_periodo_comp`),
  ADD KEY `ind_percompbancada_datas` (`dat_inicio_periodo`,`dat_fim_periodo`,`ind_excluido`),
  ADD KEY `idx_legislatura` (`num_legislatura`);

--
-- Índices de tabela `periodo_comp_comissao`
--
ALTER TABLE `periodo_comp_comissao`
  ADD PRIMARY KEY (`cod_periodo_comp`),
  ADD KEY `ind_percompcom_datas` (`dat_inicio_periodo`,`dat_fim_periodo`,`ind_excluido`);

--
-- Índices de tabela `periodo_comp_mesa`
--
ALTER TABLE `periodo_comp_mesa`
  ADD PRIMARY KEY (`cod_periodo_comp`),
  ADD KEY `ind_percompmesa_datas` (`dat_inicio_periodo`,`dat_fim_periodo`,`ind_excluido`),
  ADD KEY `idx_legislatura` (`num_legislatura`);

--
-- Índices de tabela `periodo_sessao`
--
ALTER TABLE `periodo_sessao`
  ADD PRIMARY KEY (`cod_periodo`),
  ADD UNIQUE KEY `periodo` (`num_periodo`,`num_legislatura`,`cod_sessao_leg`,`tip_sessao`),
  ADD KEY `idx_legislatura` (`num_legislatura`),
  ADD KEY `idx_sessao_leg` (`cod_sessao_leg`),
  ADD KEY `idx_tip_sessao` (`tip_sessao`),
  ADD KEY `dat_incio` (`dat_inicio`),
  ADD KEY `dat_fim` (`dat_fim`),
  ADD KEY `num_periodo` (`num_periodo`);

--
-- Índices de tabela `pessoa`
--
ALTER TABLE `pessoa`
  ADD PRIMARY KEY (`cod_pessoa`),
  ADD KEY `num_cep` (`num_cep`),
  ADD KEY `cod_logradouro` (`cod_logradouro`),
  ADD KEY `nom_cidade` (`nom_cidade`),
  ADD KEY `dat_nascimento` (`dat_nascimento`),
  ADD KEY `des_profissao` (`des_profissao`),
  ADD KEY `des_estado_civil` (`des_estado_civil`),
  ADD KEY `sex_visitante` (`sex_pessoa`),
  ADD KEY `nom_bairro` (`nom_bairro`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `nom_pessoa` (`nom_pessoa`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `nom_conjuge` (`nom_conjuge`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `idx_busca` (`doc_identidade`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `end_residencial` (`end_residencial`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `doc_identidade` (`doc_identidade`);

--
-- Índices de tabela `peticao`
--
ALTER TABLE `peticao`
  ADD PRIMARY KEY (`cod_peticao`),
  ADD KEY `cod_usuario` (`cod_usuario`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_documento` (`cod_documento`),
  ADD KEY `cod_doc_acessorio` (`cod_doc_acessorio`),
  ADD KEY `cod_norma` (`cod_norma`),
  ADD KEY `num_protocolo` (`num_protocolo`),
  ADD KEY `dat_envio` (`dat_envio`),
  ADD KEY `dat_recebimento` (`dat_recebimento`),
  ADD KEY `ind_excluido` (`ind_excluido`),
  ADD KEY `num_norma` (`num_norma`),
  ADD KEY `dat_norma` (`dat_norma`),
  ADD KEY `tip_peticionamento` (`tip_peticionamento`) USING BTREE,
  ADD KEY `cod_documento_vinculado` (`cod_documento_vinculado`);

--
-- Índices de tabela `proposicao`
--
ALTER TABLE `proposicao`
  ADD PRIMARY KEY (`cod_proposicao`),
  ADD KEY `tip_proposicao` (`tip_proposicao`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_emenda` (`cod_emenda`),
  ADD KEY `cod_substitutivo` (`cod_substitutivo`),
  ADD KEY `cod_autor` (`cod_autor`),
  ADD KEY `idx_prop_autor` (`dat_envio`,`dat_recebimento`,`ind_excluido`),
  ADD KEY `cod_parecer` (`cod_parecer`),
  ADD KEY `cod_assunto` (`cod_assunto`),
  ADD KEY `cod_assessor` (`cod_assessor`);

--
-- Índices de tabela `proposicao_geocode`
--
ALTER TABLE `proposicao_geocode`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `cod_proposicao` (`cod_proposicao`),
  ADD KEY `idx_cod_proposicao` (`cod_proposicao`);

--
-- Índices de tabela `protocolo`
--
ALTER TABLE `protocolo`
  ADD PRIMARY KEY (`cod_protocolo`),
  ADD UNIQUE KEY `idx_num_protocolo` (`num_protocolo`,`ano_protocolo`),
  ADD KEY `tip_protocolo` (`tip_protocolo`),
  ADD KEY `cod_autor` (`cod_autor`),
  ADD KEY `tip_materia` (`tip_materia`),
  ADD KEY `tip_documento` (`tip_documento`),
  ADD KEY `dat_protocolo` (`dat_protocolo`),
  ADD KEY `ano_protocolo` (`ano_protocolo`),
  ADD KEY `tip_processo` (`tip_processo`),
  ADD KEY `codigo_acesso` (`codigo_acesso`),
  ADD KEY `cod_materia_principal` (`cod_materia_principal`);
ALTER TABLE `protocolo` ADD FULLTEXT KEY `idx_busca_protocolo` (`txt_assunto_ementa`,`txt_observacao`);
ALTER TABLE `protocolo` ADD FULLTEXT KEY `txt_interessado` (`txt_interessado`);

--
-- Índices de tabela `quorum_votacao`
--
ALTER TABLE `quorum_votacao`
  ADD PRIMARY KEY (`cod_quorum`);

--
-- Índices de tabela `regime_tramitacao`
--
ALTER TABLE `regime_tramitacao`
  ADD PRIMARY KEY (`cod_regime_tramitacao`);

--
-- Índices de tabela `registro_votacao`
--
ALTER TABLE `registro_votacao`
  ADD PRIMARY KEY (`cod_votacao`),
  ADD UNIQUE KEY `idx_unique` (`cod_materia`,`cod_ordem`,`cod_emenda`,`cod_substitutivo`) USING BTREE,
  ADD KEY `cod_ordem` (`cod_ordem`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `tip_resultado_votacao` (`tip_resultado_votacao`),
  ADD KEY `cod_emenda` (`cod_emenda`),
  ADD KEY `cod_subemenda` (`cod_subemenda`),
  ADD KEY `cod_substitutivo` (`cod_substitutivo`),
  ADD KEY `cod_parecer` (`cod_parecer`);

--
-- Índices de tabela `registro_votacao_parlamentar`
--
ALTER TABLE `registro_votacao_parlamentar`
  ADD PRIMARY KEY (`cod_votacao`,`cod_parlamentar`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_votacao` (`cod_votacao`);

--
-- Índices de tabela `relatoria`
--
ALTER TABLE `relatoria`
  ADD PRIMARY KEY (`cod_relatoria`),
  ADD KEY `cod_comissao` (`cod_comissao`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `tip_fim_relatoria` (`tip_fim_relatoria`),
  ADD KEY `idx_relat_materia` (`cod_materia`,`cod_parlamentar`,`ind_excluido`),
  ADD KEY `num_protocolo` (`num_protocolo`);

--
-- Índices de tabela `reuniao_comissao`
--
ALTER TABLE `reuniao_comissao`
  ADD PRIMARY KEY (`cod_reuniao`),
  ADD KEY `cod_comissao` (`cod_comissao`);

--
-- Índices de tabela `reuniao_comissao_pauta`
--
ALTER TABLE `reuniao_comissao_pauta`
  ADD PRIMARY KEY (`cod_item`),
  ADD KEY `cod_reuniao` (`cod_reuniao`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `cod_emenda` (`cod_emenda`),
  ADD KEY `cod_substitutivo` (`cod_substitutivo`),
  ADD KEY `cod_parecer` (`cod_parecer`),
  ADD KEY `cod_relator` (`cod_relator`),
  ADD KEY `tip_resultado_votacao` (`tip_resultado_votacao`);

--
-- Índices de tabela `reuniao_comissao_presenca`
--
ALTER TABLE `reuniao_comissao_presenca`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_reuniao_parlamentar` (`cod_reuniao`,`cod_parlamentar`) USING BTREE,
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `cod_reuniao` (`cod_reuniao`);

--
-- Índices de tabela `sessao_legislativa`
--
ALTER TABLE `sessao_legislativa`
  ADD PRIMARY KEY (`cod_sessao_leg`),
  ADD KEY `idx_sessleg_datas` (`dat_inicio`,`ind_excluido`,`dat_fim`,`dat_inicio_intervalo`,`dat_fim_intervalo`),
  ADD KEY `idx_sessleg_legislatura` (`num_legislatura`,`ind_excluido`),
  ADD KEY `idx_legislatura` (`num_legislatura`);

--
-- Índices de tabela `sessao_plenaria`
--
ALTER TABLE `sessao_plenaria`
  ADD PRIMARY KEY (`cod_sessao_plen`),
  ADD KEY `cod_sessao_leg` (`cod_sessao_leg`),
  ADD KEY `tip_sessao` (`tip_sessao`),
  ADD KEY `num_legislatura` (`num_legislatura`),
  ADD KEY `dat_inicio_sessao` (`dat_inicio_sessao`),
  ADD KEY `num_sessao_plen` (`num_sessao_plen`),
  ADD KEY `cod_periodo_sessao` (`cod_periodo_sessao`);

--
-- Índices de tabela `sessao_plenaria_painel`
--
ALTER TABLE `sessao_plenaria_painel`
  ADD PRIMARY KEY (`cod_item`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`);

--
-- Índices de tabela `sessao_plenaria_presenca`
--
ALTER TABLE `sessao_plenaria_presenca`
  ADD PRIMARY KEY (`cod_presenca_sessao`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  ADD KEY `cod_sessao_plen` (`cod_sessao_plen`),
  ADD KEY `dat_sessao` (`dat_sessao`),
  ADD KEY `tip_frequencia` (`tip_frequencia`);

--
-- Índices de tabela `status_tramitacao`
--
ALTER TABLE `status_tramitacao`
  ADD PRIMARY KEY (`cod_status`),
  ADD KEY `sgl_status` (`sgl_status`);
ALTER TABLE `status_tramitacao` ADD FULLTEXT KEY `des_status` (`des_status`);

--
-- Índices de tabela `status_tramitacao_administrativo`
--
ALTER TABLE `status_tramitacao_administrativo`
  ADD PRIMARY KEY (`cod_status`),
  ADD KEY `sgl_status` (`sgl_status`);
ALTER TABLE `status_tramitacao_administrativo` ADD FULLTEXT KEY `des_status` (`des_status`);

--
-- Índices de tabela `subemenda`
--
ALTER TABLE `subemenda`
  ADD PRIMARY KEY (`cod_subemenda`),
  ADD UNIQUE KEY `numsub_emenda` (`num_subemenda`,`tip_subemenda`,`cod_emenda`,`ind_excluido`),
  ADD KEY `idx_cod_autor` (`cod_autor`),
  ADD KEY `idx_cod_emenda` (`cod_emenda`),
  ADD KEY `tip_subemenda` (`tip_subemenda`);
ALTER TABLE `subemenda` ADD FULLTEXT KEY `idx_txt_ementa` (`txt_ementa`);

--
-- Índices de tabela `substitutivo`
--
ALTER TABLE `substitutivo`
  ADD PRIMARY KEY (`cod_substitutivo`),
  ADD KEY `idx_cod_materia` (`cod_materia`),
  ADD KEY `idx_substitutivo` (`cod_substitutivo`,`cod_materia`) USING BTREE,
  ADD KEY `cod_autor` (`cod_autor`);
ALTER TABLE `substitutivo` ADD FULLTEXT KEY `idx_txt_ementa` (`txt_ementa`);
ALTER TABLE `substitutivo` ADD FULLTEXT KEY `txt_observacao` (`txt_observacao`);

--
-- Índices de tabela `tipo_afastamento`
--
ALTER TABLE `tipo_afastamento`
  ADD PRIMARY KEY (`tip_afastamento`);

--
-- Índices de tabela `tipo_autor`
--
ALTER TABLE `tipo_autor`
  ADD PRIMARY KEY (`tip_autor`),
  ADD KEY `des_tipo_autor` (`des_tipo_autor`);

--
-- Índices de tabela `tipo_comissao`
--
ALTER TABLE `tipo_comissao`
  ADD PRIMARY KEY (`tip_comissao`),
  ADD KEY `nom_tipo_comissao` (`nom_tipo_comissao`),
  ADD KEY `sgl_natureza_comissao` (`sgl_natureza_comissao`);

--
-- Índices de tabela `tipo_dependente`
--
ALTER TABLE `tipo_dependente`
  ADD PRIMARY KEY (`tip_dependente`),
  ADD KEY `des_tipo_dependente` (`des_tipo_dependente`);

--
-- Índices de tabela `tipo_documento`
--
ALTER TABLE `tipo_documento`
  ADD PRIMARY KEY (`tip_documento`),
  ADD KEY `des_tipo_documento` (`des_tipo_documento`);

--
-- Índices de tabela `tipo_documento_administrativo`
--
ALTER TABLE `tipo_documento_administrativo`
  ADD PRIMARY KEY (`tip_documento`),
  ADD KEY `des_tipo_documento` (`des_tipo_documento`),
  ADD KEY `ind_publico` (`ind_publico`);

--
-- Índices de tabela `tipo_emenda`
--
ALTER TABLE `tipo_emenda`
  ADD PRIMARY KEY (`tip_emenda`),
  ADD KEY `des_tipo_emenda` (`des_tipo_emenda`);

--
-- Índices de tabela `tipo_expediente`
--
ALTER TABLE `tipo_expediente`
  ADD PRIMARY KEY (`cod_expediente`),
  ADD KEY `nom_expediente` (`nom_expediente`);

--
-- Índices de tabela `tipo_fim_relatoria`
--
ALTER TABLE `tipo_fim_relatoria`
  ADD PRIMARY KEY (`tip_fim_relatoria`);

--
-- Índices de tabela `tipo_instituicao`
--
ALTER TABLE `tipo_instituicao`
  ADD PRIMARY KEY (`tip_instituicao`);

--
-- Índices de tabela `tipo_materia_legislativa`
--
ALTER TABLE `tipo_materia_legislativa`
  ADD PRIMARY KEY (`tip_materia`),
  ADD KEY `des_tipo_materia` (`des_tipo_materia`);

--
-- Índices de tabela `tipo_norma_juridica`
--
ALTER TABLE `tipo_norma_juridica`
  ADD PRIMARY KEY (`tip_norma`),
  ADD KEY `des_tipo_norma` (`des_tipo_norma`);

--
-- Índices de tabela `tipo_peticionamento`
--
ALTER TABLE `tipo_peticionamento`
  ADD PRIMARY KEY (`tip_peticionamento`),
  ADD KEY `cod_unid_tram_dest` (`cod_unid_tram_dest`);

--
-- Índices de tabela `tipo_proposicao`
--
ALTER TABLE `tipo_proposicao`
  ADD PRIMARY KEY (`tip_proposicao`),
  ADD KEY `des_tipo_proposicao` (`des_tipo_proposicao`);

--
-- Índices de tabela `tipo_resultado_votacao`
--
ALTER TABLE `tipo_resultado_votacao`
  ADD PRIMARY KEY (`tip_resultado_votacao`),
  ADD KEY `nom_resultado` (`nom_resultado`);

--
-- Índices de tabela `tipo_sessao_plenaria`
--
ALTER TABLE `tipo_sessao_plenaria`
  ADD PRIMARY KEY (`tip_sessao`),
  ADD KEY `nom_sessao` (`nom_sessao`);

--
-- Índices de tabela `tipo_situacao_materia`
--
ALTER TABLE `tipo_situacao_materia`
  ADD PRIMARY KEY (`tip_situacao_materia`),
  ADD KEY `des_tipo_situacao` (`des_tipo_situacao`);

--
-- Índices de tabela `tipo_situacao_militar`
--
ALTER TABLE `tipo_situacao_militar`
  ADD PRIMARY KEY (`tip_situacao_militar`);

--
-- Índices de tabela `tipo_situacao_norma`
--
ALTER TABLE `tipo_situacao_norma`
  ADD PRIMARY KEY (`tip_situacao_norma`),
  ADD KEY `des_tipo_situacao` (`des_tipo_situacao`);

--
-- Índices de tabela `tipo_vinculo_norma`
--
ALTER TABLE `tipo_vinculo_norma`
  ADD PRIMARY KEY (`cod_tip_vinculo`),
  ADD UNIQUE KEY `tipo_vinculo` (`tipo_vinculo`),
  ADD UNIQUE KEY `idx_vinculo` (`tipo_vinculo`,`des_vinculo`,`des_vinculo_passivo`,`ind_excluido`),
  ADD KEY `tip_situacao` (`tip_situacao`);

--
-- Índices de tabela `tipo_votacao`
--
ALTER TABLE `tipo_votacao`
  ADD PRIMARY KEY (`tip_votacao`);

--
-- Índices de tabela `tramitacao`
--
ALTER TABLE `tramitacao`
  ADD PRIMARY KEY (`cod_tramitacao`),
  ADD KEY `cod_unid_tram_local` (`cod_unid_tram_local`),
  ADD KEY `cod_unid_tram_dest` (`cod_unid_tram_dest`),
  ADD KEY `cod_status` (`cod_status`),
  ADD KEY `cod_materia` (`cod_materia`),
  ADD KEY `idx_tramit_ultmat` (`ind_ult_tramitacao`,`dat_tramitacao`,`cod_materia`,`ind_excluido`),
  ADD KEY `sgl_turno` (`sgl_turno`),
  ADD KEY `cod_usuario_local` (`cod_usuario_local`),
  ADD KEY `cod_usuario_dest` (`cod_usuario_dest`);

--
-- Índices de tabela `tramitacao_administrativo`
--
ALTER TABLE `tramitacao_administrativo`
  ADD PRIMARY KEY (`cod_tramitacao`),
  ADD KEY `cod_unid_tram_dest` (`cod_unid_tram_dest`),
  ADD KEY `tramitacao_ind1` (`ind_ult_tramitacao`),
  ADD KEY `cod_unid_tram_local` (`cod_unid_tram_local`),
  ADD KEY `cod_status` (`cod_status`),
  ADD KEY `cod_documento` (`cod_documento`),
  ADD KEY `cod_usuario_local` (`cod_usuario_local`),
  ADD KEY `cod_usuario_dest` (`cod_usuario_dest`);

--
-- Índices de tabela `turno_discussao`
--
ALTER TABLE `turno_discussao`
  ADD PRIMARY KEY (`cod_turno`),
  ADD UNIQUE KEY `idx_unique_key` (`cod_turno`,`sgl_turno`,`ind_excluido`);

--
-- Índices de tabela `unidade_tramitacao`
--
ALTER TABLE `unidade_tramitacao`
  ADD PRIMARY KEY (`cod_unid_tramitacao`),
  ADD KEY `idx_unidtramit_orgao` (`cod_orgao`,`ind_excluido`),
  ADD KEY `idx_unidtramit_comissao` (`cod_comissao`,`ind_excluido`),
  ADD KEY `cod_orgao` (`cod_orgao`),
  ADD KEY `cod_comissao` (`cod_comissao`),
  ADD KEY `idx_unidtramit_parlamentar` (`cod_parlamentar`,`ind_excluido`),
  ADD KEY `cod_parlamentar` (`cod_parlamentar`),
  ADD KEY `ind_leg` (`ind_leg`),
  ADD KEY `ind_adm` (`ind_adm`),
  ADD KEY `ind_leg_2` (`ind_leg`),
  ADD KEY `ind_adm_2` (`ind_adm`);

--
-- Índices de tabela `usuario`
--
ALTER TABLE `usuario`
  ADD PRIMARY KEY (`cod_usuario`),
  ADD KEY `idx_col_username` (`col_username`),
  ADD KEY `idx_cod_localidade` (`cod_localidade_resid`),
  ADD KEY `ind_ativo` (`ind_ativo`),
  ADD KEY `ind_interno` (`ind_interno`);

--
-- Índices de tabela `usuario_peticionamento`
--
ALTER TABLE `usuario_peticionamento`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_usuario` (`cod_usuario`),
  ADD KEY `idx_tip_peticionamento` (`tip_peticionamento`) USING BTREE;

--
-- Índices de tabela `usuario_tipo_documento`
--
ALTER TABLE `usuario_tipo_documento`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_usuario` (`cod_usuario`),
  ADD KEY `idx_tip_documento` (`tip_documento`) USING BTREE;

--
-- Índices de tabela `usuario_unid_tram`
--
ALTER TABLE `usuario_unid_tram`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_usuario` (`cod_usuario`),
  ADD KEY `idx_unid_tramitacao` (`cod_unid_tramitacao`);

--
-- Índices de tabela `vinculo_norma_juridica`
--
ALTER TABLE `vinculo_norma_juridica`
  ADD PRIMARY KEY (`cod_vinculo`),
  ADD KEY `tip_vinculo` (`tip_vinculo`),
  ADD KEY `idx_vnj_norma_referente` (`cod_norma_referente`,`cod_norma_referida`,`ind_excluido`),
  ADD KEY `idx_vnj_norma_referida` (`cod_norma_referida`,`cod_norma_referente`,`ind_excluido`),
  ADD KEY `cod_norma_referente` (`cod_norma_referente`),
  ADD KEY `cod_norma_referida` (`cod_norma_referida`);

--
-- Índices de tabela `visita`
--
ALTER TABLE `visita`
  ADD PRIMARY KEY (`cod_visita`),
  ADD KEY `cod_funcionario` (`cod_funcionario`),
  ADD KEY `cod_pessoa` (`cod_pessoa`) USING BTREE,
  ADD KEY `dat_entrada` (`dat_entrada`),
  ADD KEY `des_situacao` (`des_situacao`);

--
-- AUTO_INCREMENT para tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `acomp_materia`
--
ALTER TABLE `acomp_materia`
  MODIFY `cod_cadastro` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `afastamento`
--
ALTER TABLE `afastamento`
  MODIFY `cod_afastamento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `anexada`
--
ALTER TABLE `anexada`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `anexo_norma`
--
ALTER TABLE `anexo_norma`
  MODIFY `cod_anexo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_armario`
--
ALTER TABLE `arquivo_armario`
  MODIFY `cod_armario` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_corredor`
--
ALTER TABLE `arquivo_corredor`
  MODIFY `cod_corredor` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_item`
--
ALTER TABLE `arquivo_item`
  MODIFY `cod_item` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_prateleira`
--
ALTER TABLE `arquivo_prateleira`
  MODIFY `cod_prateleira` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_recipiente`
--
ALTER TABLE `arquivo_recipiente`
  MODIFY `cod_recipiente` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_tipo_recipiente`
--
ALTER TABLE `arquivo_tipo_recipiente`
  MODIFY `tip_recipiente` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_tipo_suporte`
--
ALTER TABLE `arquivo_tipo_suporte`
  MODIFY `tip_suporte` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_tipo_tit_documental`
--
ALTER TABLE `arquivo_tipo_tit_documental`
  MODIFY `tip_tit_documental` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `arquivo_unidade`
--
ALTER TABLE `arquivo_unidade`
  MODIFY `cod_unidade` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `assessor_parlamentar`
--
ALTER TABLE `assessor_parlamentar`
  MODIFY `cod_assessor` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `assinatura_documento`
--
ALTER TABLE `assinatura_documento`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `assinatura_storage`
--
ALTER TABLE `assinatura_storage`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `assunto_materia`
--
ALTER TABLE `assunto_materia`
  MODIFY `cod_assunto` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `assunto_norma`
--
ALTER TABLE `assunto_norma`
  MODIFY `cod_assunto` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `assunto_proposicao`
--
ALTER TABLE `assunto_proposicao`
  MODIFY `cod_assunto` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `autor`
--
ALTER TABLE `autor`
  MODIFY `cod_autor` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `autoria`
--
ALTER TABLE `autoria`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `autoria_emenda`
--
ALTER TABLE `autoria_emenda`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `autoria_substitutivo`
--
ALTER TABLE `autoria_substitutivo`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `bancada`
--
ALTER TABLE `bancada`
  MODIFY `cod_bancada` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `cargo_bancada`
--
ALTER TABLE `cargo_bancada`
  MODIFY `cod_cargo` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `cargo_comissao`
--
ALTER TABLE `cargo_comissao`
  MODIFY `cod_cargo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `cargo_executivo`
--
ALTER TABLE `cargo_executivo`
  MODIFY `cod_cargo` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `cargo_mesa`
--
ALTER TABLE `cargo_mesa`
  MODIFY `cod_cargo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `coautoria_proposicao`
--
ALTER TABLE `coautoria_proposicao`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `coligacao`
--
ALTER TABLE `coligacao`
  MODIFY `cod_coligacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `comissao`
--
ALTER TABLE `comissao`
  MODIFY `cod_comissao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `composicao_bancada`
--
ALTER TABLE `composicao_bancada`
  MODIFY `cod_comp_bancada` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `composicao_coligacao`
--
ALTER TABLE `composicao_coligacao`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `composicao_comissao`
--
ALTER TABLE `composicao_comissao`
  MODIFY `cod_comp_comissao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `composicao_executivo`
--
ALTER TABLE `composicao_executivo`
  MODIFY `cod_composicao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `composicao_mesa`
--
ALTER TABLE `composicao_mesa`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `dependente`
--
ALTER TABLE `dependente`
  MODIFY `cod_dependente` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `despacho_inicial`
--
ALTER TABLE `despacho_inicial`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `destinatario_oficio`
--
ALTER TABLE `destinatario_oficio`
  MODIFY `cod_destinatario` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `documento_acessorio`
--
ALTER TABLE `documento_acessorio`
  MODIFY `cod_documento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `documento_acessorio_administrativo`
--
ALTER TABLE `documento_acessorio_administrativo`
  MODIFY `cod_documento_acessorio` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `documento_administrativo`
--
ALTER TABLE `documento_administrativo`
  MODIFY `cod_documento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `documento_administrativo_materia`
--
ALTER TABLE `documento_administrativo_materia`
  MODIFY `cod_vinculo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `documento_administrativo_vinculado`
--
ALTER TABLE `documento_administrativo_vinculado`
  MODIFY `cod_vinculo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `documento_comissao`
--
ALTER TABLE `documento_comissao`
  MODIFY `cod_documento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `emenda`
--
ALTER TABLE `emenda`
  MODIFY `cod_emenda` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `encerramento_presenca`
--
ALTER TABLE `encerramento_presenca`
  MODIFY `cod_presenca_encerramento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `expediente_discussao`
--
ALTER TABLE `expediente_discussao`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `expediente_materia`
--
ALTER TABLE `expediente_materia`
  MODIFY `cod_ordem` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `expediente_presenca`
--
ALTER TABLE `expediente_presenca`
  MODIFY `cod_presenca_expediente` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `expediente_sessao_plenaria`
--
ALTER TABLE `expediente_sessao_plenaria`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `filiacao`
--
ALTER TABLE `filiacao`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `funcionario`
--
ALTER TABLE `funcionario`
  MODIFY `cod_funcionario` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `gabinete_atendimento`
--
ALTER TABLE `gabinete_atendimento`
  MODIFY `cod_atendimento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `gabinete_eleitor`
--
ALTER TABLE `gabinete_eleitor`
  MODIFY `cod_eleitor` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `instituicao`
--
ALTER TABLE `instituicao`
  MODIFY `cod_instituicao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `legislacao_citada`
--
ALTER TABLE `legislacao_citada`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `legislatura`
--
ALTER TABLE `legislatura`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `lexml_registro_provedor`
--
ALTER TABLE `lexml_registro_provedor`
  MODIFY `cod_provedor` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `lexml_registro_publicador`
--
ALTER TABLE `lexml_registro_publicador`
  MODIFY `cod_publicador` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `liderancas_partidarias`
--
ALTER TABLE `liderancas_partidarias`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `logradouro`
--
ALTER TABLE `logradouro`
  MODIFY `cod_logradouro` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `mandato`
--
ALTER TABLE `mandato`
  MODIFY `cod_mandato` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `materia_apresentada_sessao`
--
ALTER TABLE `materia_apresentada_sessao`
  MODIFY `cod_ordem` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `materia_legislativa`
--
ALTER TABLE `materia_legislativa`
  MODIFY `cod_materia` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `mesa_sessao_plenaria`
--
ALTER TABLE `mesa_sessao_plenaria`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `nivel_instrucao`
--
ALTER TABLE `nivel_instrucao`
  MODIFY `cod_nivel_instrucao` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `norma_juridica`
--
ALTER TABLE `norma_juridica`
  MODIFY `cod_norma` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `numeracao`
--
ALTER TABLE `numeracao`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `oradores`
--
ALTER TABLE `oradores`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `oradores_expediente`
--
ALTER TABLE `oradores_expediente`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `ordem_dia`
--
ALTER TABLE `ordem_dia`
  MODIFY `cod_ordem` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `ordem_dia_discussao`
--
ALTER TABLE `ordem_dia_discussao`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `ordem_dia_presenca`
--
ALTER TABLE `ordem_dia_presenca`
  MODIFY `cod_presenca_ordem_dia` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `orgao`
--
ALTER TABLE `orgao`
  MODIFY `cod_orgao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `origem`
--
ALTER TABLE `origem`
  MODIFY `cod_origem` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `parlamentar`
--
ALTER TABLE `parlamentar`
  MODIFY `cod_parlamentar` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `partido`
--
ALTER TABLE `partido`
  MODIFY `cod_partido` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `periodo_comp_bancada`
--
ALTER TABLE `periodo_comp_bancada`
  MODIFY `cod_periodo_comp` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `periodo_comp_comissao`
--
ALTER TABLE `periodo_comp_comissao`
  MODIFY `cod_periodo_comp` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `periodo_comp_mesa`
--
ALTER TABLE `periodo_comp_mesa`
  MODIFY `cod_periodo_comp` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `periodo_sessao`
--
ALTER TABLE `periodo_sessao`
  MODIFY `cod_periodo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `pessoa`
--
ALTER TABLE `pessoa`
  MODIFY `cod_pessoa` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `peticao`
--
ALTER TABLE `peticao`
  MODIFY `cod_peticao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `proposicao`
--
ALTER TABLE `proposicao`
  MODIFY `cod_proposicao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `proposicao_geocode`
--
ALTER TABLE `proposicao_geocode`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `protocolo`
--
ALTER TABLE `protocolo`
  MODIFY `cod_protocolo` int(7) UNSIGNED ZEROFILL NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `quorum_votacao`
--
ALTER TABLE `quorum_votacao`
  MODIFY `cod_quorum` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `regime_tramitacao`
--
ALTER TABLE `regime_tramitacao`
  MODIFY `cod_regime_tramitacao` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `registro_votacao`
--
ALTER TABLE `registro_votacao`
  MODIFY `cod_votacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `relatoria`
--
ALTER TABLE `relatoria`
  MODIFY `cod_relatoria` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `reuniao_comissao`
--
ALTER TABLE `reuniao_comissao`
  MODIFY `cod_reuniao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `reuniao_comissao_pauta`
--
ALTER TABLE `reuniao_comissao_pauta`
  MODIFY `cod_item` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `reuniao_comissao_presenca`
--
ALTER TABLE `reuniao_comissao_presenca`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `sessao_legislativa`
--
ALTER TABLE `sessao_legislativa`
  MODIFY `cod_sessao_leg` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `sessao_plenaria`
--
ALTER TABLE `sessao_plenaria`
  MODIFY `cod_sessao_plen` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `sessao_plenaria_painel`
--
ALTER TABLE `sessao_plenaria_painel`
  MODIFY `cod_item` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `sessao_plenaria_presenca`
--
ALTER TABLE `sessao_plenaria_presenca`
  MODIFY `cod_presenca_sessao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `status_tramitacao`
--
ALTER TABLE `status_tramitacao`
  MODIFY `cod_status` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `status_tramitacao_administrativo`
--
ALTER TABLE `status_tramitacao_administrativo`
  MODIFY `cod_status` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `subemenda`
--
ALTER TABLE `subemenda`
  MODIFY `cod_subemenda` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `substitutivo`
--
ALTER TABLE `substitutivo`
  MODIFY `cod_substitutivo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_afastamento`
--
ALTER TABLE `tipo_afastamento`
  MODIFY `tip_afastamento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_comissao`
--
ALTER TABLE `tipo_comissao`
  MODIFY `tip_comissao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_dependente`
--
ALTER TABLE `tipo_dependente`
  MODIFY `tip_dependente` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_documento`
--
ALTER TABLE `tipo_documento`
  MODIFY `tip_documento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_documento_administrativo`
--
ALTER TABLE `tipo_documento_administrativo`
  MODIFY `tip_documento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_emenda`
--
ALTER TABLE `tipo_emenda`
  MODIFY `tip_emenda` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_expediente`
--
ALTER TABLE `tipo_expediente`
  MODIFY `cod_expediente` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_fim_relatoria`
--
ALTER TABLE `tipo_fim_relatoria`
  MODIFY `tip_fim_relatoria` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_instituicao`
--
ALTER TABLE `tipo_instituicao`
  MODIFY `tip_instituicao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_materia_legislativa`
--
ALTER TABLE `tipo_materia_legislativa`
  MODIFY `tip_materia` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_norma_juridica`
--
ALTER TABLE `tipo_norma_juridica`
  MODIFY `tip_norma` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_peticionamento`
--
ALTER TABLE `tipo_peticionamento`
  MODIFY `tip_peticionamento` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_proposicao`
--
ALTER TABLE `tipo_proposicao`
  MODIFY `tip_proposicao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_resultado_votacao`
--
ALTER TABLE `tipo_resultado_votacao`
  MODIFY `tip_resultado_votacao` int UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_sessao_plenaria`
--
ALTER TABLE `tipo_sessao_plenaria`
  MODIFY `tip_sessao` tinyint NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_situacao_materia`
--
ALTER TABLE `tipo_situacao_materia`
  MODIFY `tip_situacao_materia` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_situacao_norma`
--
ALTER TABLE `tipo_situacao_norma`
  MODIFY `tip_situacao_norma` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_vinculo_norma`
--
ALTER TABLE `tipo_vinculo_norma`
  MODIFY `cod_tip_vinculo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tipo_votacao`
--
ALTER TABLE `tipo_votacao`
  MODIFY `tip_votacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tramitacao`
--
ALTER TABLE `tramitacao`
  MODIFY `cod_tramitacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `tramitacao_administrativo`
--
ALTER TABLE `tramitacao_administrativo`
  MODIFY `cod_tramitacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `turno_discussao`
--
ALTER TABLE `turno_discussao`
  MODIFY `cod_turno` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `unidade_tramitacao`
--
ALTER TABLE `unidade_tramitacao`
  MODIFY `cod_unid_tramitacao` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `usuario`
--
ALTER TABLE `usuario`
  MODIFY `cod_usuario` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `usuario_peticionamento`
--
ALTER TABLE `usuario_peticionamento`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `usuario_tipo_documento`
--
ALTER TABLE `usuario_tipo_documento`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `usuario_unid_tram`
--
ALTER TABLE `usuario_unid_tram`
  MODIFY `id` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `vinculo_norma_juridica`
--
ALTER TABLE `vinculo_norma_juridica`
  MODIFY `cod_vinculo` int NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `visita`
--
ALTER TABLE `visita`
  MODIFY `cod_visita` int NOT NULL AUTO_INCREMENT;

--
-- Restrições para tabelas despejadas
--

--
-- Restrições para tabelas `afastamento`
--
ALTER TABLE `afastamento`
  ADD CONSTRAINT `afastamento_ibfk_1` FOREIGN KEY (`cod_mandato`) REFERENCES `mandato` (`cod_mandato`) ON DELETE CASCADE ON UPDATE RESTRICT,
  ADD CONSTRAINT `afastamento_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE,
  ADD CONSTRAINT `afastamento_ibfk_5` FOREIGN KEY (`tip_afastamento`) REFERENCES `tipo_afastamento` (`tip_afastamento`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `afastamento_ibfk_6` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `anexada`
--
ALTER TABLE `anexada`
  ADD CONSTRAINT `anexada_ibfk_1` FOREIGN KEY (`cod_materia_anexada`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `anexada_ibfk_2` FOREIGN KEY (`cod_materia_principal`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

--
-- Restrições para tabelas `anexo_norma`
--
ALTER TABLE `anexo_norma`
  ADD CONSTRAINT `anexo_norma_ibfk_1` FOREIGN KEY (`cod_norma`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

--
-- Restrições para tabelas `assessor_parlamentar`
--
ALTER TABLE `assessor_parlamentar`
  ADD CONSTRAINT `assessor_parlamentar_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE;

--
-- Restrições para tabelas `assinatura_documento`
--
ALTER TABLE `assinatura_documento`
  ADD CONSTRAINT `assinatura_documento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `assunto_proposicao`
--
ALTER TABLE `assunto_proposicao`
  ADD CONSTRAINT `assunto_proposicao_ibfk_1` FOREIGN KEY (`tip_proposicao`) REFERENCES `tipo_proposicao` (`tip_proposicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `autor`
--
ALTER TABLE `autor`
  ADD CONSTRAINT `autor_ibfk_1` FOREIGN KEY (`cod_bancada`) REFERENCES `bancada` (`cod_bancada`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_2` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_3` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_4` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_5` FOREIGN KEY (`tip_autor`) REFERENCES `tipo_autor` (`tip_autor`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `autoria`
--
ALTER TABLE `autoria`
  ADD CONSTRAINT `autoria_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `autoria_ibfk_2` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `autoria_emenda`
--
ALTER TABLE `autoria_emenda`
  ADD CONSTRAINT `autoria_emenda_ibfk_1` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autoria_emenda_ibfk_2` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE CASCADE;

--
-- Restrições para tabelas `autoria_substitutivo`
--
ALTER TABLE `autoria_substitutivo`
  ADD CONSTRAINT `autoria_substitutivo_ibfk_1` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autoria_substitutivo_ibfk_2` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE CASCADE;

--
-- Restrições para tabelas `bancada`
--
ALTER TABLE `bancada`
  ADD CONSTRAINT `bancada_ibfk_1` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT,
  ADD CONSTRAINT `bancada_ibfk_2` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `coligacao`
--
ALTER TABLE `coligacao`
  ADD CONSTRAINT `coligacao_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `comissao`
--
ALTER TABLE `comissao`
  ADD CONSTRAINT `comissao_ibfk_1` FOREIGN KEY (`tip_comissao`) REFERENCES `tipo_comissao` (`tip_comissao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `composicao_bancada`
--
ALTER TABLE `composicao_bancada`
  ADD CONSTRAINT `composicao_bancada_ibfk_1` FOREIGN KEY (`cod_bancada`) REFERENCES `bancada` (`cod_bancada`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_bancada_ibfk_2` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_bancada` (`cod_cargo`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_bancada_ibfk_3` FOREIGN KEY (`cod_periodo_comp`) REFERENCES `periodo_comp_bancada` (`cod_periodo_comp`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_bancada_ibfk_4` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `composicao_coligacao`
--
ALTER TABLE `composicao_coligacao`
  ADD CONSTRAINT `composicao_coligacao_ibfk_1` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `composicao_comissao`
--
ALTER TABLE `composicao_comissao`
  ADD CONSTRAINT `composicao_comissao_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`),
  ADD CONSTRAINT `composicao_comissao_ibfk_3` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `composicao_comissao_ibfk_4` FOREIGN KEY (`cod_periodo_comp`) REFERENCES `periodo_comp_comissao` (`cod_periodo_comp`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_comissao_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_comissao` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `composicao_executivo`
--
ALTER TABLE `composicao_executivo`
  ADD CONSTRAINT `composicao_executivo_ibfk_2` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_executivo` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `composicao_executivo_ibfk_3` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `composicao_executivo_ibfk_4` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `composicao_mesa`
--
ALTER TABLE `composicao_mesa`
  ADD CONSTRAINT `composicao_mesa_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_mesa_ibfk_3` FOREIGN KEY (`cod_periodo_comp`) REFERENCES `periodo_comp_mesa` (`cod_periodo_comp`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_mesa_ibfk_4` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_mesa_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_mesa` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `dependente`
--
ALTER TABLE `dependente`
  ADD CONSTRAINT `dependente_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `dependente_ibfk_2` FOREIGN KEY (`tip_dependente`) REFERENCES `tipo_dependente` (`tip_dependente`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `despacho_inicial`
--
ALTER TABLE `despacho_inicial`
  ADD CONSTRAINT `despacho_inicial_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `despacho_inicial_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

--
-- Restrições para tabelas `destinatario_oficio`
--
ALTER TABLE `destinatario_oficio`
  ADD CONSTRAINT `destinatario_oficio_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `destinatario_oficio_ibfk_2` FOREIGN KEY (`cod_instituicao`) REFERENCES `instituicao` (`cod_instituicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `documento_acessorio`
--
ALTER TABLE `documento_acessorio`
  ADD CONSTRAINT `documento_acessorio_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `documento_acessorio_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento` (`tip_documento`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `documento_acessorio_administrativo`
--
ALTER TABLE `documento_acessorio_administrativo`
  ADD CONSTRAINT `documento_acessorio_administrativo_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `documento_acessorio_administrativo_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `documento_administrativo`
--
ALTER TABLE `documento_administrativo`
  ADD CONSTRAINT `documento_administrativo_ibfk_1` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `documento_administrativo_materia`
--
ALTER TABLE `documento_administrativo_materia`
  ADD CONSTRAINT `documento_administrativo_materia_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE,
  ADD CONSTRAINT `documento_administrativo_materia_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

--
-- Restrições para tabelas `documento_administrativo_vinculado`
--
ALTER TABLE `documento_administrativo_vinculado`
  ADD CONSTRAINT `documento_administrativo_vinculado_ibfk_1` FOREIGN KEY (`cod_documento_vinculado`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE,
  ADD CONSTRAINT `documento_administrativo_vinculado_ibfk_2` FOREIGN KEY (`cod_documento_vinculante`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE;

--
-- Restrições para tabelas `documento_comissao`
--
ALTER TABLE `documento_comissao`
  ADD CONSTRAINT `documento_comissao_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `emenda`
--
ALTER TABLE `emenda`
  ADD CONSTRAINT `emenda_ibfk_1` FOREIGN KEY (`tip_emenda`) REFERENCES `tipo_emenda` (`tip_emenda`) ON DELETE RESTRICT,
  ADD CONSTRAINT `emenda_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

--
-- Restrições para tabelas `encerramento_presenca`
--
ALTER TABLE `encerramento_presenca`
  ADD CONSTRAINT `encerramento_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `encerramento_presenca_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE;

--
-- Restrições para tabelas `expediente_discussao`
--
ALTER TABLE `expediente_discussao`
  ADD CONSTRAINT `expediente_discussao_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `fk_cod_ordem` FOREIGN KEY (`cod_ordem`) REFERENCES `expediente_materia` (`cod_ordem`) ON DELETE CASCADE;

--
-- Restrições para tabelas `expediente_materia`
--
ALTER TABLE `expediente_materia`
  ADD CONSTRAINT `expediente_materia_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_2` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_3` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `expediente_materia_ibfk_4` FOREIGN KEY (`tip_quorum`) REFERENCES `quorum_votacao` (`cod_quorum`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_5` FOREIGN KEY (`tip_votacao`) REFERENCES `tipo_votacao` (`tip_votacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_6` FOREIGN KEY (`tip_turno`) REFERENCES `turno_discussao` (`cod_turno`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `expediente_presenca`
--
ALTER TABLE `expediente_presenca`
  ADD CONSTRAINT `expediente_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_presenca_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE;

--
-- Restrições para tabelas `expediente_sessao_plenaria`
--
ALTER TABLE `expediente_sessao_plenaria`
  ADD CONSTRAINT `expediente_sessao_plenaria_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `expediente_sessao_plenaria_ibfk_2` FOREIGN KEY (`cod_expediente`) REFERENCES `tipo_expediente` (`cod_expediente`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `filiacao`
--
ALTER TABLE `filiacao`
  ADD CONSTRAINT `filiacao_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `filiacao_ibfk_2` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `funcionario`
--
ALTER TABLE `funcionario`
  ADD CONSTRAINT `funcionario_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `gabinete_atendimento`
--
ALTER TABLE `gabinete_atendimento`
  ADD CONSTRAINT `gabinete_atendimento_ibfk_1` FOREIGN KEY (`cod_eleitor`) REFERENCES `gabinete_eleitor` (`cod_eleitor`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `gabinete_atendimento_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Restrições para tabelas `gabinete_eleitor`
--
ALTER TABLE `gabinete_eleitor`
  ADD CONSTRAINT `gabinete_eleitor_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `gabinete_eleitor_ibfk_2` FOREIGN KEY (`cod_assessor`) REFERENCES `assessor_parlamentar` (`cod_assessor`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `instituicao`
--
ALTER TABLE `instituicao`
  ADD CONSTRAINT `instituicao_ibfk_2` FOREIGN KEY (`tip_instituicao`) REFERENCES `tipo_instituicao` (`tip_instituicao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `instituicao_ibfk_3` FOREIGN KEY (`cod_localidade`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `legislacao_citada`
--
ALTER TABLE `legislacao_citada`
  ADD CONSTRAINT `legislacao_citada_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `legislacao_citada_ibfk_2` FOREIGN KEY (`cod_norma`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

--
-- Restrições para tabelas `liderancas_partidarias`
--
ALTER TABLE `liderancas_partidarias`
  ADD CONSTRAINT `liderancas_partidarias_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `liderancas_partidarias_ibfk_2` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT,
  ADD CONSTRAINT `liderancas_partidarias_ibfk_3` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `logradouro`
--
ALTER TABLE `logradouro`
  ADD CONSTRAINT `logradouro_ibfk_1` FOREIGN KEY (`cod_localidade`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT,
  ADD CONSTRAINT `logradouro_ibfk_2` FOREIGN KEY (`cod_norma`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

--
-- Restrições para tabelas `mandato`
--
ALTER TABLE `mandato`
  ADD CONSTRAINT `mandato_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE,
  ADD CONSTRAINT `mandato_ibfk_3` FOREIGN KEY (`cod_coligacao`) REFERENCES `coligacao` (`cod_coligacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `mandato_ibfk_4` FOREIGN KEY (`tip_afastamento`) REFERENCES `tipo_afastamento` (`tip_afastamento`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mandato_ibfk_5` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `materia_apresentada_sessao`
--
ALTER TABLE `materia_apresentada_sessao`
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_2` FOREIGN KEY (`cod_doc_acessorio`) REFERENCES `documento_acessorio` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_3` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_4` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_5` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_6` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_7` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `materia_legislativa`
--
ALTER TABLE `materia_legislativa`
  ADD CONSTRAINT `materia_legislativa_ibfk_2` FOREIGN KEY (`cod_local_origem_externa`) REFERENCES `origem` (`cod_origem`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_legislativa_ibfk_3` FOREIGN KEY (`tip_quorum`) REFERENCES `quorum_votacao` (`cod_quorum`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_legislativa_ibfk_4` FOREIGN KEY (`cod_regime_tramitacao`) REFERENCES `regime_tramitacao` (`cod_regime_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_legislativa_ibfk_5` FOREIGN KEY (`tip_id_basica`) REFERENCES `tipo_materia_legislativa` (`tip_materia`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `mesa_sessao_plenaria`
--
ALTER TABLE `mesa_sessao_plenaria`
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_3` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_4` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_mesa` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `norma_juridica`
--
ALTER TABLE `norma_juridica`
  ADD CONSTRAINT `norma_juridica_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE SET NULL,
  ADD CONSTRAINT `norma_juridica_ibfk_2` FOREIGN KEY (`cod_situacao`) REFERENCES `tipo_situacao_norma` (`tip_situacao_norma`) ON DELETE SET NULL ON UPDATE RESTRICT,
  ADD CONSTRAINT `norma_juridica_ibfk_3` FOREIGN KEY (`tip_norma`) REFERENCES `tipo_norma_juridica` (`tip_norma`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `numeracao`
--
ALTER TABLE `numeracao`
  ADD CONSTRAINT `numeracao_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `numeracao_ibfk_2` FOREIGN KEY (`tip_materia`) REFERENCES `tipo_materia_legislativa` (`tip_materia`) ON DELETE CASCADE;

--
-- Restrições para tabelas `oradores`
--
ALTER TABLE `oradores`
  ADD CONSTRAINT `oradores_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `oradores_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `oradores_expediente`
--
ALTER TABLE `oradores_expediente`
  ADD CONSTRAINT `oradores_expediente_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `oradores_expediente_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `ordem_dia`
--
ALTER TABLE `ordem_dia`
  ADD CONSTRAINT `ordem_dia_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `ordem_dia_ibfk_3` FOREIGN KEY (`tip_quorum`) REFERENCES `quorum_votacao` (`cod_quorum`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_4` FOREIGN KEY (`tip_votacao`) REFERENCES `tipo_votacao` (`tip_votacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_5` FOREIGN KEY (`tip_turno`) REFERENCES `turno_discussao` (`cod_turno`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_6` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `ordem_dia_discussao`
--
ALTER TABLE `ordem_dia_discussao`
  ADD CONSTRAINT `ordem_dia_discussao_ibfk_1` FOREIGN KEY (`cod_ordem`) REFERENCES `ordem_dia` (`cod_ordem`) ON DELETE CASCADE,
  ADD CONSTRAINT `ordem_dia_discussao_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `ordem_dia_presenca`
--
ALTER TABLE `ordem_dia_presenca`
  ADD CONSTRAINT `ordem_dia_presenca_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `ordem_dia_presenca_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `parecer`
--
ALTER TABLE `parecer`
  ADD CONSTRAINT `parecer_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `parecer_ibfk_2` FOREIGN KEY (`cod_relatoria`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE CASCADE;

--
-- Restrições para tabelas `parlamentar`
--
ALTER TABLE `parlamentar`
  ADD CONSTRAINT `parlamentar_ibfk_1` FOREIGN KEY (`cod_localidade_resid`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT,
  ADD CONSTRAINT `parlamentar_ibfk_2` FOREIGN KEY (`cod_nivel_instrucao`) REFERENCES `nivel_instrucao` (`cod_nivel_instrucao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `parlamentar_ibfk_3` FOREIGN KEY (`tip_situacao_militar`) REFERENCES `tipo_situacao_militar` (`tip_situacao_militar`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `periodo_comp_bancada`
--
ALTER TABLE `periodo_comp_bancada`
  ADD CONSTRAINT `periodo_comp_bancada_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `periodo_comp_mesa`
--
ALTER TABLE `periodo_comp_mesa`
  ADD CONSTRAINT `periodo_comp_mesa_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `periodo_sessao`
--
ALTER TABLE `periodo_sessao`
  ADD CONSTRAINT `periodo_sessao_ibfk_1` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `periodo_sessao_ibfk_2` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `periodo_sessao_ibfk_3` FOREIGN KEY (`tip_sessao`) REFERENCES `tipo_sessao_plenaria` (`tip_sessao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `peticao`
--
ALTER TABLE `peticao`
  ADD CONSTRAINT `peticao_ibfk_1` FOREIGN KEY (`tip_peticionamento`) REFERENCES `tipo_peticionamento` (`tip_peticionamento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_2` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_3` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_4` FOREIGN KEY (`cod_doc_acessorio`) REFERENCES `documento_acessorio` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_5` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_7` FOREIGN KEY (`cod_documento_vinculado`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `proposicao`
--
ALTER TABLE `proposicao`
  ADD CONSTRAINT `proposicao_ibfk_1` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE SET NULL,
  ADD CONSTRAINT `proposicao_ibfk_2` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_3` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE SET NULL,
  ADD CONSTRAINT `proposicao_ibfk_4` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE SET NULL,
  ADD CONSTRAINT `proposicao_ibfk_5` FOREIGN KEY (`tip_proposicao`) REFERENCES `tipo_proposicao` (`tip_proposicao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_6` FOREIGN KEY (`cod_assunto`) REFERENCES `assunto_proposicao` (`cod_assunto`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_7` FOREIGN KEY (`cod_assessor`) REFERENCES `assessor_parlamentar` (`cod_assessor`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `proposicao_geocode`
--
ALTER TABLE `proposicao_geocode`
  ADD CONSTRAINT `proposicao_geocode_ibfk_1` FOREIGN KEY (`cod_proposicao`) REFERENCES `proposicao` (`cod_proposicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `protocolo`
--
ALTER TABLE `protocolo`
  ADD CONSTRAINT `protocolo_ibfk_1` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `protocolo_ibfk_2` FOREIGN KEY (`cod_materia_principal`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE SET NULL;

--
-- Restrições para tabelas `registro_votacao`
--
ALTER TABLE `registro_votacao`
  ADD CONSTRAINT `registro_votacao_ibfk_1` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE RESTRICT,
  ADD CONSTRAINT `registro_votacao_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `registro_votacao_ibfk_3` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `registro_votacao_ibfk_4` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `registro_votacao_parlamentar`
--
ALTER TABLE `registro_votacao_parlamentar`
  ADD CONSTRAINT `registro_votacao_parlamentar_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `registro_votacao_parlamentar_ibfk_2` FOREIGN KEY (`cod_votacao`) REFERENCES `registro_votacao` (`cod_votacao`) ON DELETE CASCADE;

--
-- Restrições para tabelas `relatoria`
--
ALTER TABLE `relatoria`
  ADD CONSTRAINT `relatoria_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `relatoria_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `relatoria_ibfk_3` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `relatoria_ibfk_4` FOREIGN KEY (`tip_fim_relatoria`) REFERENCES `tipo_fim_relatoria` (`tip_fim_relatoria`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `reuniao_comissao`
--
ALTER TABLE `reuniao_comissao`
  ADD CONSTRAINT `reuniao_comissao_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `reuniao_comissao_pauta`
--
ALTER TABLE `reuniao_comissao_pauta`
  ADD CONSTRAINT `reuniao_comissao_pauta_ibfk_1` FOREIGN KEY (`cod_reuniao`) REFERENCES `reuniao_comissao` (`cod_reuniao`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `reuniao_comissao_pauta_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `reuniao_comissao_pauta_ibfk_3` FOREIGN KEY (`cod_relator`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `reuniao_comissao_presenca`
--
ALTER TABLE `reuniao_comissao_presenca`
  ADD CONSTRAINT `reuniao_comissao_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `reuniao_comissao_presenca_ibfk_2` FOREIGN KEY (`cod_reuniao`) REFERENCES `reuniao_comissao` (`cod_reuniao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `sessao_legislativa`
--
ALTER TABLE `sessao_legislativa`
  ADD CONSTRAINT `sessao_legislativa_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `sessao_plenaria`
--
ALTER TABLE `sessao_plenaria`
  ADD CONSTRAINT `sessao_plenaria_ibfk_1` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_ibfk_2` FOREIGN KEY (`tip_sessao`) REFERENCES `tipo_sessao_plenaria` (`tip_sessao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_ibfk_3` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_ibfk_4` FOREIGN KEY (`cod_periodo_sessao`) REFERENCES `periodo_sessao` (`cod_periodo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `sessao_plenaria_painel`
--
ALTER TABLE `sessao_plenaria_painel`
  ADD CONSTRAINT `sessao_plenaria_painel_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `sessao_plenaria_presenca`
--
ALTER TABLE `sessao_plenaria_presenca`
  ADD CONSTRAINT `sessao_plenaria_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_presenca_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE;

--
-- Restrições para tabelas `substitutivo`
--
ALTER TABLE `substitutivo`
  ADD CONSTRAINT `substitutivo_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

--
-- Restrições para tabelas `tramitacao`
--
ALTER TABLE `tramitacao`
  ADD CONSTRAINT `tramitacao_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `tramitacao_ibfk_2` FOREIGN KEY (`cod_status`) REFERENCES `status_tramitacao` (`cod_status`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_3` FOREIGN KEY (`cod_unid_tram_local`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_4` FOREIGN KEY (`cod_unid_tram_dest`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_5` FOREIGN KEY (`cod_usuario_local`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_6` FOREIGN KEY (`cod_usuario_dest`) REFERENCES `usuario` (`cod_usuario`) ON DELETE SET NULL;

--
-- Restrições para tabelas `tramitacao_administrativo`
--
ALTER TABLE `tramitacao_administrativo`
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_2` FOREIGN KEY (`cod_status`) REFERENCES `status_tramitacao_administrativo` (`cod_status`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_3` FOREIGN KEY (`cod_unid_tram_dest`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_4` FOREIGN KEY (`cod_unid_tram_local`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_5` FOREIGN KEY (`cod_usuario_local`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_6` FOREIGN KEY (`cod_usuario_dest`) REFERENCES `usuario` (`cod_usuario`) ON DELETE SET NULL;

--
-- Restrições para tabelas `unidade_tramitacao`
--
ALTER TABLE `unidade_tramitacao`
  ADD CONSTRAINT `unidade_tramitacao_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `unidade_tramitacao_ibfk_2` FOREIGN KEY (`cod_orgao`) REFERENCES `orgao` (`cod_orgao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `unidade_tramitacao_ibfk_3` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `usuario`
--
ALTER TABLE `usuario`
  ADD CONSTRAINT `usuario_ibfk_1` FOREIGN KEY (`cod_localidade_resid`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `usuario_peticionamento`
--
ALTER TABLE `usuario_peticionamento`
  ADD CONSTRAINT `usuario_peticionamento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `usuario_peticionamento_ibfk_2` FOREIGN KEY (`tip_peticionamento`) REFERENCES `tipo_peticionamento` (`tip_peticionamento`) ON DELETE RESTRICT;

--
-- Restrições para tabelas `usuario_tipo_documento`
--
ALTER TABLE `usuario_tipo_documento`
  ADD CONSTRAINT `usuario_tipo_documento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `usuario_tipo_documento_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT;

--
-- Restrições para tabelas `usuario_unid_tram`
--
ALTER TABLE `usuario_unid_tram`
  ADD CONSTRAINT `usuario_unid_tram_ibfk_1` FOREIGN KEY (`cod_unid_tramitacao`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE CASCADE,
  ADD CONSTRAINT `usuario_unid_tram_ibfk_2` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE CASCADE;

--
-- Restrições para tabelas `vinculo_norma_juridica`
--
ALTER TABLE `vinculo_norma_juridica`
  ADD CONSTRAINT `vinculo_norma_juridica_ibfk_1` FOREIGN KEY (`cod_norma_referente`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE,
  ADD CONSTRAINT `vinculo_norma_juridica_ibfk_2` FOREIGN KEY (`cod_norma_referida`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

--
-- Restrições para tabelas `visita`
--
ALTER TABLE `visita`
  ADD CONSTRAINT `visita_ibfk_2` FOREIGN KEY (`cod_pessoa`) REFERENCES `pessoa` (`cod_pessoa`) ON DELETE CASCADE,
  ADD CONSTRAINT `visita_ibfk_3` FOREIGN KEY (`cod_funcionario`) REFERENCES `funcionario` (`cod_funcionario`) ON DELETE RESTRICT ON UPDATE RESTRICT;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
