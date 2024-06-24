SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;


CREATE TABLE IF NOT EXISTS `acomp_materia` (
  `cod_cadastro` int NOT NULL AUTO_INCREMENT,
  `cod_materia` int NOT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_hash` varchar(8) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_cadastro`),
  UNIQUE KEY `fk_{CCECA63D-5992-437B-BCD3-D7C98DA3E926}` (`cod_materia`,`end_email`),
  KEY `cod_materia` (`cod_materia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `afastamento` (
  `cod_afastamento` int NOT NULL AUTO_INCREMENT,
  `cod_parlamentar` int NOT NULL,
  `cod_mandato` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `tip_afastamento` int NOT NULL,
  `dat_inicio_afastamento` date NOT NULL,
  `dat_fim_afastamento` date DEFAULT NULL,
  `cod_parlamentar_suplente` int NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_afastamento`),
  KEY `idx_parlamentar_mandato` (`cod_parlamentar`,`num_legislatura`),
  KEY `idx_afastamento_datas` (`cod_parlamentar`,`dat_inicio_afastamento`,`dat_fim_afastamento`),
  KEY `idx_tip_afastamento` (`tip_afastamento`),
  KEY `idx__parlamentar_suplente` (`cod_parlamentar_suplente`,`num_legislatura`),
  KEY `cod_mandato` (`cod_mandato`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `num_legislatura` (`num_legislatura`),
  KEY `cod_parlamentar_suplente` (`cod_parlamentar_suplente`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `anexada` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_materia_principal` int NOT NULL,
  `cod_materia_anexada` int NOT NULL,
  `dat_anexacao` date NOT NULL,
  `dat_desanexacao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_materia_anexada` (`cod_materia_anexada`),
  KEY `idx_materia_principal` (`cod_materia_principal`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `anexo_norma` (
  `cod_anexo` int NOT NULL AUTO_INCREMENT,
  `cod_norma` int NOT NULL,
  `txt_descricao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_anexo`),
  KEY `cod_norma` (`cod_norma`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_armario` (
  `cod_armario` int NOT NULL AUTO_INCREMENT,
  `cod_corredor` int DEFAULT NULL,
  `cod_unidade` int NOT NULL,
  `nom_armario` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_armario`),
  KEY `cod_corredor` (`cod_corredor`),
  KEY `cod_unidade` (`cod_unidade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_corredor` (
  `cod_corredor` int NOT NULL AUTO_INCREMENT,
  `cod_unidade` int NOT NULL,
  `nom_corredor` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_corredor`),
  KEY `cod_unidade` (`cod_unidade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_item` (
  `cod_item` int NOT NULL AUTO_INCREMENT,
  `cod_recipiente` int NOT NULL,
  `tip_suporte` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_norma` int DEFAULT NULL,
  `cod_documento` int DEFAULT NULL,
  `cod_protocolo` int(7) UNSIGNED ZEROFILL DEFAULT NULL,
  `des_item` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_arquivamento` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_item`),
  KEY `cod_recipiente` (`cod_recipiente`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_norma` (`cod_norma`),
  KEY `cod_documento` (`cod_documento`),
  KEY `cod_protocolo` (`cod_protocolo`),
  KEY `tip_suporte` (`tip_suporte`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_prateleira` (
  `cod_prateleira` int NOT NULL AUTO_INCREMENT,
  `cod_armario` int DEFAULT NULL,
  `cod_corredor` int DEFAULT NULL,
  `cod_unidade` int NOT NULL,
  `nom_prateleira` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_prateleira`),
  KEY `cod_armario` (`cod_armario`),
  KEY `cod_corredor` (`cod_corredor`),
  KEY `cod_unidade` (`cod_unidade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_recipiente` (
  `cod_recipiente` int NOT NULL AUTO_INCREMENT,
  `tip_recipiente` int NOT NULL,
  `num_recipiente` varchar(11) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tip_tit_documental` int NOT NULL,
  `ano_recipiente` int NOT NULL,
  `dat_recipiente` date NOT NULL,
  `cod_corredor` int DEFAULT NULL,
  `cod_armario` int DEFAULT NULL,
  `cod_prateleira` int DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `num_folha_recipiente` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_recipiente`),
  UNIQUE KEY `num_tipo_recipiente` (`num_recipiente`,`tip_recipiente`,`ano_recipiente`,`ind_excluido`),
  KEY `tip_recipiente` (`tip_recipiente`),
  KEY `tip_tit_documental` (`tip_tit_documental`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_tipo_recipiente` (
  `tip_recipiente` int NOT NULL AUTO_INCREMENT,
  `des_tipo_recipiente` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_recipiente`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_tipo_suporte` (
  `tip_suporte` int NOT NULL AUTO_INCREMENT,
  `des_tipo_suporte` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_suporte`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_tipo_tit_documental` (
  `tip_tit_documental` int NOT NULL AUTO_INCREMENT,
  `sgl_tip_tit_documental` varchar(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_tipo_tit_documental` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_tit_documental`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `arquivo_unidade` (
  `cod_unidade` int NOT NULL AUTO_INCREMENT,
  `tip_extensao_atuacao` int NOT NULL,
  `tip_estagio_evolucao` int NOT NULL,
  `nom_unidade` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_localizacao` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_unidade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `assessor_parlamentar` (
  `cod_assessor` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_assessor`),
  UNIQUE KEY `assessor_parlamentar` (`cod_assessor`,`cod_parlamentar`,`ind_excluido`),
  KEY `cod_parlamentar` (`cod_parlamentar`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `assinatura_documento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_assinatura_doc` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `codigo` int NOT NULL,
  `anexo` int DEFAULT NULL,
  `tipo_doc` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_solicitante` int DEFAULT NULL,
  `dat_solicitacao` datetime NOT NULL,
  `cod_usuario` int NOT NULL,
  `dat_assinatura` datetime DEFAULT NULL,
  `dat_recusa` datetime DEFAULT NULL,
  `ind_assinado` int NOT NULL DEFAULT '0',
  `ind_recusado` int NOT NULL DEFAULT '0',
  `ind_separado` int NOT NULL DEFAULT '0',
  `txt_motivo_recusa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_prim_assinatura` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_cod_assinatura_doc` (`cod_assinatura_doc`,`codigo`,`tipo_doc`,`cod_usuario`) USING BTREE,
  KEY `ind_assinado` (`ind_assinado`),
  KEY `ind_recusado` (`ind_recusado`),
  KEY `assinatura_documento_ibfk` (`cod_usuario`) USING BTREE,
  KEY `tipo_doc` (`tipo_doc`),
  KEY `cod_solicitante` (`cod_solicitante`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `assinatura_storage` (
  `id` int NOT NULL AUTO_INCREMENT,
  `tip_documento` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pdf_location` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `storage_path` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pdf_file` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pdf_signed` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `tip_documento` (`tip_documento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `assunto_materia` (
  `cod_assunto` int NOT NULL AUTO_INCREMENT,
  `des_assunto` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_estendida` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_assunto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `assunto_norma` (
  `cod_assunto` int NOT NULL AUTO_INCREMENT,
  `des_assunto` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_estendida` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_assunto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `assunto_proposicao` (
  `cod_assunto` int NOT NULL AUTO_INCREMENT,
  `tip_proposicao` int NOT NULL,
  `des_assunto` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nom_orgao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `end_orgao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_assunto`),
  KEY `tip_proposicao` (`tip_proposicao`),
  KEY `des_assunto` (`des_assunto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `autor` (
  `cod_autor` int NOT NULL AUTO_INCREMENT,
  `cod_partido` int DEFAULT NULL,
  `cod_comissao` int DEFAULT NULL,
  `cod_bancada` int DEFAULT NULL,
  `cod_parlamentar` int DEFAULT NULL,
  `tip_autor` int NOT NULL,
  `nom_autor` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `col_username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_autor`),
  KEY `idx_tip_autor` (`tip_autor`),
  KEY `idx_parlamentar` (`cod_parlamentar`),
  KEY `idx_comissao` (`cod_comissao`),
  KEY `idx_partido` (`cod_partido`),
  KEY `idx_bancada` (`cod_bancada`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `autoria` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_autor` int NOT NULL,
  `cod_materia` int NOT NULL,
  `ind_primeiro_autor` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_materia` (`cod_materia`),
  KEY `idx_autor` (`cod_autor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `autoria_emenda` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_autor` int NOT NULL,
  `cod_emenda` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_autor` (`cod_autor`),
  KEY `idx_emenda` (`cod_emenda`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `autoria_substitutivo` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_autor` int NOT NULL,
  `cod_substitutivo` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_autor` (`cod_autor`),
  KEY `idx_substitutivo` (`cod_substitutivo`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `bancada` (
  `cod_bancada` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `cod_partido` int DEFAULT NULL,
  `nom_bancada` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `descricao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_criacao` date DEFAULT NULL,
  `dat_extincao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_bancada`),
  KEY `idt_nom_bancada` (`nom_bancada`),
  KEY `num_legislatura` (`num_legislatura`),
  KEY `cod_partido` (`cod_partido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `cargo_bancada` (
  `cod_cargo` int NOT NULL AUTO_INCREMENT,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unico` int NOT NULL DEFAULT '0',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_cargo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `cargo_comissao` (
  `cod_cargo` int NOT NULL AUTO_INCREMENT,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unico` int NOT NULL DEFAULT '0',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_cargo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `cargo_executivo` (
  `cod_cargo` tinyint NOT NULL AUTO_INCREMENT,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_cargo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `cargo_mesa` (
  `cod_cargo` int NOT NULL AUTO_INCREMENT,
  `des_cargo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unico` int NOT NULL DEFAULT '1',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_cargo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `categoria_instituicao` (
  `tip_instituicao` int NOT NULL,
  `cod_categoria` int NOT NULL,
  `des_categoria` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_categoria`,`tip_instituicao`) USING BTREE,
  KEY `tip_instituicao` (`tip_instituicao`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `coligacao` (
  `cod_coligacao` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `nom_coligacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_votos_coligacao` int DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_coligacao`),
  KEY `idx_legislatura` (`num_legislatura`),
  KEY `idx_coligacao_legislatura` (`num_legislatura`,`ind_excluido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `comissao` (
  `cod_comissao` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_comissao`),
  KEY `idx_comissao_tipo` (`tip_comissao`),
  KEY `idx_comissao_nome` (`nom_comissao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `composicao_bancada` (
  `cod_comp_bancada` int NOT NULL AUTO_INCREMENT,
  `cod_parlamentar` int NOT NULL,
  `cod_bancada` int NOT NULL,
  `cod_periodo_comp` int DEFAULT NULL,
  `cod_cargo` int NOT NULL,
  `ind_titular` int NOT NULL,
  `dat_designacao` date NOT NULL,
  `dat_desligamento` date DEFAULT NULL,
  `des_motivo_desligamento` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `obs_composicao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_comp_bancada`),
  KEY `idx_cargo` (`cod_cargo`),
  KEY `idx_bancada` (`cod_bancada`),
  KEY `idx_parlamentar` (`cod_parlamentar`),
  KEY `cod_periodo_comp` (`cod_periodo_comp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `composicao_coligacao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_partido` int NOT NULL,
  `cod_coligacao` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_coligacao` (`cod_coligacao`),
  KEY `idx_partido` (`cod_partido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `composicao_comissao` (
  `cod_comp_comissao` int NOT NULL AUTO_INCREMENT,
  `cod_parlamentar` int NOT NULL,
  `cod_comissao` int NOT NULL,
  `cod_periodo_comp` int NOT NULL,
  `cod_cargo` int NOT NULL,
  `ind_titular` int NOT NULL DEFAULT '1',
  `dat_designacao` date NOT NULL,
  `dat_desligamento` date DEFAULT NULL,
  `des_motivo_desligamento` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `obs_composicao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_comp_comissao`),
  KEY `idx_cargo` (`cod_cargo`),
  KEY `idx_periodo_comp` (`cod_periodo_comp`),
  KEY `idx_comissao` (`cod_comissao`),
  KEY `idx_parlamentar` (`cod_parlamentar`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `composicao_executivo` (
  `cod_composicao` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `nom_completo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_cargo` tinyint NOT NULL,
  `cod_partido` int DEFAULT NULL,
  `dat_inicio_mandato` date DEFAULT NULL,
  `dat_fim_mandato` date DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_composicao`),
  KEY `num_legislatura` (`num_legislatura`),
  KEY `cod_cargo` (`cod_cargo`),
  KEY `cod_partido` (`cod_partido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `composicao_mesa` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_parlamentar` int NOT NULL,
  `cod_sessao_leg` int DEFAULT NULL,
  `cod_periodo_comp` int NOT NULL,
  `cod_cargo` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_cargo` (`cod_cargo`),
  KEY `idx_periodo_comp` (`cod_periodo_comp`),
  KEY `idx_parlamentar` (`cod_parlamentar`),
  KEY `cod_sessao_leg` (`cod_sessao_leg`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `dependente` (
  `cod_dependente` int NOT NULL AUTO_INCREMENT,
  `tip_dependente` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `nom_dependente` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sex_dependente` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `num_cpf` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_rg` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_dependente`),
  KEY `idx_dep_parlam` (`tip_dependente`,`cod_parlamentar`,`ind_excluido`),
  KEY `idx_dependente` (`tip_dependente`),
  KEY `idx_parlamentar` (`cod_parlamentar`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `despacho_inicial` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_materia` int NOT NULL,
  `num_ordem` int UNSIGNED NOT NULL,
  `cod_comissao` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_unique` (`cod_materia`,`num_ordem`),
  KEY `idx_comissao` (`cod_comissao`),
  KEY `idx_materia` (`cod_materia`),
  KEY `idx_despinic_comissao` (`cod_materia`,`num_ordem`,`cod_comissao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `destinatario_oficio` (
  `cod_destinatario` int NOT NULL AUTO_INCREMENT,
  `cod_documento` int NOT NULL,
  `cod_instituicao` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_destinatario`),
  KEY `cod_documento` (`cod_documento`),
  KEY `cod_instituicao` (`cod_instituicao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `documento_acessorio` (
  `cod_documento` int NOT NULL AUTO_INCREMENT,
  `cod_materia` int NOT NULL,
  `tip_documento` int NOT NULL,
  `nom_documento` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_documento` datetime DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `nom_autor_documento` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_publico` int NOT NULL DEFAULT '1',
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_documento`),
  KEY `idx_tip_documento` (`tip_documento`),
  KEY `idx_materia` (`cod_materia`),
  KEY `ind_publico` (`ind_publico`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `documento_acessorio_administrativo` (
  `cod_documento_acessorio` int NOT NULL AUTO_INCREMENT,
  `cod_documento` int NOT NULL DEFAULT '0',
  `tip_documento` int NOT NULL DEFAULT '0',
  `nom_documento` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_arquivo` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_documento` datetime DEFAULT NULL,
  `nom_autor_documento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_assunto` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_documento_acessorio`),
  KEY `idx_tip_documento` (`tip_documento`),
  KEY `idx_documento` (`cod_documento`),
  KEY `idx_autor_documento` (`nom_autor_documento`),
  KEY `idx_dat_documento` (`dat_documento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `documento_administrativo` (
  `cod_documento` int NOT NULL AUTO_INCREMENT,
  `tip_documento` int NOT NULL,
  `num_documento` int NOT NULL,
  `ano_documento` int NOT NULL DEFAULT '0',
  `dat_documento` date NOT NULL,
  `num_protocolo` int DEFAULT NULL,
  `txt_interessado` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_autor` int DEFAULT NULL,
  `cod_entidade` int DEFAULT NULL,
  `cod_materia` int DEFAULT NULL,
  `num_dias_prazo` int DEFAULT NULL,
  `dat_fim_prazo` date DEFAULT NULL,
  `ind_tramitacao` int NOT NULL DEFAULT '0',
  `txt_assunto` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `cod_situacao` int DEFAULT NULL,
  `cod_assunto` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_documento`),
  KEY `tip_documento` (`tip_documento`,`num_documento`,`ano_documento`),
  KEY `cod_situacao` (`cod_situacao`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_entidade` (`cod_entidade`),
  KEY `cod_autor` (`cod_autor`),
  KEY `ano_documento` (`ano_documento`),
  KEY `dat_documento` (`dat_documento`),
  KEY `num_protocolo` (`num_protocolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `documento_administrativo_materia` (
  `cod_vinculo` int NOT NULL AUTO_INCREMENT,
  `cod_documento` int NOT NULL,
  `cod_materia` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_vinculo`),
  KEY `idx_cod_documento` (`cod_documento`),
  KEY `idx_cod_materia` (`cod_materia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `documento_administrativo_vinculado` (
  `cod_vinculo` int NOT NULL AUTO_INCREMENT,
  `cod_documento_vinculante` int NOT NULL,
  `cod_documento_vinculado` int NOT NULL,
  `dat_vinculacao` datetime DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_vinculo`),
  UNIQUE KEY `idx_doc_vinculo` (`cod_documento_vinculante`,`cod_documento_vinculado`),
  KEY `idx_doc_vinculado` (`cod_documento_vinculado`) USING BTREE,
  KEY `idx_cod_documento` (`cod_documento_vinculante`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `documento_comissao` (
  `cod_documento` int NOT NULL AUTO_INCREMENT,
  `cod_comissao` int NOT NULL,
  `dat_documento` date NOT NULL,
  `txt_descricao` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_observacao` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_documento`),
  KEY `cod_comissao` (`cod_comissao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `emenda` (
  `cod_emenda` int NOT NULL AUTO_INCREMENT,
  `tip_emenda` int NOT NULL,
  `num_emenda` int NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_autor` int DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `exc_pauta` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_emenda`),
  KEY `idx_cod_materia` (`cod_materia`),
  KEY `idx_tip_emenda` (`tip_emenda`),
  KEY `idx_emenda` (`cod_emenda`,`tip_emenda`,`cod_materia`) USING BTREE,
  KEY `cod_autor` (`cod_autor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `encerramento_presenca` (
  `cod_presenca_encerramento` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL DEFAULT '0',
  `cod_parlamentar` int NOT NULL,
  `dat_ordem` date NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_presenca_encerramento`),
  UNIQUE KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `dat_ordem` (`dat_ordem`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `expediente_discussao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_ordem` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `cod_ordem` (`cod_ordem`),
  KEY `cod_parlamentar` (`cod_parlamentar`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `expediente_materia` (
  `cod_ordem` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_ordem`),
  KEY `idx_exped_datord` (`dat_ordem`,`ind_excluido`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `cod_materia` (`cod_materia`),
  KEY `tip_votacao` (`tip_votacao`),
  KEY `tip_quorum` (`tip_quorum`),
  KEY `cod_parecer` (`cod_parecer`),
  KEY `tip_turno` (`tip_turno`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `expediente_presenca` (
  `cod_presenca_expediente` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL DEFAULT '0',
  `cod_parlamentar` int NOT NULL,
  `dat_ordem` date NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_presenca_expediente`),
  UNIQUE KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `dat_ordem` (`dat_ordem`,`ind_excluido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `expediente_sessao_plenaria` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL,
  `cod_expediente` int NOT NULL,
  `txt_expediente` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `cod_expediente` (`cod_expediente`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `filiacao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `dat_filiacao` date NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_partido` int NOT NULL,
  `dat_desfiliacao` date DEFAULT NULL,
  `ind_excluido` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_partido` (`cod_partido`),
  KEY `idx_parlamentar` (`cod_parlamentar`),
  KEY `dat_filiacao` (`dat_filiacao`),
  KEY `dat_desfiliacao` (`dat_desfiliacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `funcionario` (
  `cod_funcionario` int NOT NULL AUTO_INCREMENT,
  `nom_funcionario` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cod_usuario` int DEFAULT NULL,
  `des_cargo` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_cadastro` date NOT NULL,
  `ind_ativo` int NOT NULL DEFAULT '1',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_funcionario`),
  KEY `cod_usuario` (`cod_usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gabinete_atendimento` (
  `cod_atendimento` int NOT NULL AUTO_INCREMENT,
  `cod_parlamentar` int NOT NULL,
  `cod_eleitor` int NOT NULL,
  `dat_atendimento` date NOT NULL,
  `txt_assunto` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `dat_resultado` date DEFAULT NULL,
  `txt_resultado` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_atendente` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_atendimento`),
  KEY `idx_resultado` (`txt_resultado`) USING BTREE,
  KEY `idx_eleitor` (`cod_eleitor`) USING BTREE,
  KEY `idx_parlamentar` (`cod_parlamentar`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gabinete_eleitor` (
  `cod_eleitor` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_eleitor`),
  KEY `sex_eleitor` (`sex_eleitor`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_assessor` (`cod_assessor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `instituicao` (
  `cod_instituicao` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  `dat_insercao` datetime DEFAULT NULL,
  `txt_user_insercao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ip_insercao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `timestamp_alteracao` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `txt_user_alteracao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ip_alteracao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`cod_instituicao`),
  KEY `tip_instituicao` (`tip_instituicao`),
  KEY `cod_categoria` (`cod_categoria`),
  KEY `cod_localidade` (`cod_localidade`),
  KEY `ind_excluido` (`ind_excluido`),
  KEY `idx_cod_cat` (`tip_instituicao`,`cod_categoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `legislacao_citada` (
  `id` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `cod_norma` (`cod_norma`),
  KEY `cod_materia` (`cod_materia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `legislatura` (
  `id` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `dat_inicio` date NOT NULL,
  `dat_fim` date NOT NULL,
  `dat_eleicao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `num_legislatura` (`num_legislatura`),
  KEY `idx_legislatura_datas` (`dat_inicio`,`dat_fim`,`dat_eleicao`,`ind_excluido`),
  KEY `num_legislatura_2` (`num_legislatura`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `lexml_registro_provedor` (
  `cod_provedor` int NOT NULL AUTO_INCREMENT,
  `id_provedor` int NOT NULL,
  `nom_provedor` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_provedor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `adm_email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_responsavel` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_responsavel` int DEFAULT NULL,
  `xml_provedor` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`cod_provedor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `lexml_registro_publicador` (
  `cod_publicador` int NOT NULL AUTO_INCREMENT,
  `id_publicador` int NOT NULL,
  `nom_publicador` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `adm_email` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sigla` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_responsavel` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `id_responsavel` int NOT NULL,
  PRIMARY KEY (`cod_publicador`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `liderancas_partidarias` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_partido` int NOT NULL,
  `num_ordem` tinyint NOT NULL,
  `url_discurso` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_num_ordem` (`cod_sessao_plen`,`num_ordem`,`ind_excluido`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `cod_partido` (`cod_partido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `localidade` (
  `cod_localidade` int NOT NULL DEFAULT '0',
  `nom_localidade` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_localidade_pesq` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_localidade` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_uf` char(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_regiao` char(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_localidade`),
  KEY `nom_localidade` (`nom_localidade`),
  KEY `sgl_uf` (`sgl_uf`),
  KEY `tip_localidade` (`tip_localidade`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `logradouro` (
  `cod_logradouro` int NOT NULL AUTO_INCREMENT,
  `nom_logradouro` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nom_bairro` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_cep` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_localidade` int DEFAULT NULL,
  `cod_norma` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_logradouro`),
  KEY `num_cep` (`num_cep`),
  KEY `cod_localidade` (`cod_localidade`),
  KEY `logradouro_ibfk_2` (`cod_norma`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `mandato` (
  `cod_mandato` int NOT NULL AUTO_INCREMENT,
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
  `ind_titular` int NOT NULL DEFAULT '1',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_mandato`),
  KEY `idx_coligacao` (`cod_coligacao`),
  KEY `idx_parlamentar` (`cod_parlamentar`),
  KEY `idx_afastamento` (`tip_afastamento`),
  KEY `idx_mandato_legislatura` (`num_legislatura`,`cod_parlamentar`,`ind_excluido`),
  KEY `idx_legislatura` (`num_legislatura`),
  KEY `tip_causa_fim_mandato` (`tip_causa_fim_mandato`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `materia_apresentada_sessao` (
  `cod_ordem` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_ordem`),
  KEY `fk_cod_materia` (`cod_materia`),
  KEY `idx_apres_datord` (`dat_ordem`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `idx_cod_documento` (`cod_documento`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_materia_2` (`cod_materia`),
  KEY `cod_emenda` (`cod_emenda`),
  KEY `cod_substitutivo` (`cod_substitutivo`),
  KEY `cod_doc_acessorio` (`cod_doc_acessorio`),
  KEY `cod_parecer` (`cod_parecer`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `materia_legislativa` (
  `cod_materia` int NOT NULL AUTO_INCREMENT,
  `tip_id_basica` int NOT NULL,
  `num_protocolo` int DEFAULT NULL,
  `num_ident_basica` int NOT NULL,
  `ano_ident_basica` int NOT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `tip_apresentacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_regime_tramitacao` int NOT NULL,
  `dat_publicacao` date DEFAULT NULL,
  `des_veiculo_publicacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_origem_externa` int DEFAULT NULL,
  `num_origem_externa` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ano_origem_externa` int DEFAULT NULL,
  `dat_origem_externa` date DEFAULT NULL,
  `cod_local_origem_externa` int DEFAULT NULL,
  `nom_apelido` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_dias_prazo` int DEFAULT NULL,
  `dat_fim_prazo` date DEFAULT NULL,
  `ind_tramitacao` int NOT NULL,
  `ind_polemica` int DEFAULT NULL,
  `des_objeto` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_complementar` int DEFAULT NULL,
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
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_materia`),
  KEY `cod_local_origem_externa` (`cod_local_origem_externa`),
  KEY `tip_origem_externa` (`tip_origem_externa`),
  KEY `cod_regime_tramitacao` (`cod_regime_tramitacao`),
  KEY `idx_dat_apresentacao` (`dat_apresentacao`,`tip_id_basica`,`ind_excluido`),
  KEY `idx_matleg_dat_publicacao` (`dat_publicacao`,`tip_id_basica`,`ind_excluido`),
  KEY `cod_situacao` (`cod_situacao`),
  KEY `idx_mat_principal` (`cod_materia_principal`),
  KEY `tip_quorum` (`tip_quorum`),
  KEY `tip_id_basica` (`tip_id_basica`) USING BTREE,
  KEY `idx_matleg_ident` (`ind_excluido`,`tip_id_basica`,`ano_ident_basica`,`num_ident_basica`) USING BTREE,
  KEY `idx_tramitacao` (`ind_tramitacao`) USING BTREE,
  KEY `idx_assunto` (`cod_assunto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `mesa_sessao_plenaria` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_cargo` int NOT NULL,
  `cod_sessao_leg` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `cod_sessao_plen` int NOT NULL,
  `ind_excluido` int UNSIGNED DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cod_sessao_leg` (`cod_sessao_leg`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_cargo` (`cod_cargo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `nivel_instrucao` (
  `cod_nivel_instrucao` int NOT NULL AUTO_INCREMENT,
  `des_nivel_instrucao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_nivel_instrucao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `norma_juridica` (
  `cod_norma` int NOT NULL AUTO_INCREMENT,
  `tip_norma` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `num_norma` int NOT NULL,
  `ano_norma` int NOT NULL,
  `tip_esfera_federacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_norma` date DEFAULT NULL,
  `dat_publicacao` date DEFAULT NULL,
  `des_veiculo_publicacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_pag_inicio_publ` int DEFAULT NULL,
  `num_pag_fim_publ` int DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_indexacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_complemento` int DEFAULT NULL,
  `cod_assunto` char(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cod_situacao` int DEFAULT NULL,
  `dat_vigencia` date DEFAULT NULL,
  `timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `ind_publico` int NOT NULL DEFAULT '0',
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_norma`),
  KEY `cod_assunto` (`cod_assunto`),
  KEY `tip_norma` (`tip_norma`),
  KEY `cod_materia` (`cod_materia`),
  KEY `idx_ano_numero` (`ano_norma`,`num_norma`,`ind_excluido`),
  KEY `dat_norma` (`dat_norma`),
  KEY `cod_situacao` (`cod_situacao`),
  KEY `ind_publico` (`ind_publico`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `numeracao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_materia` int NOT NULL,
  `num_ordem` int NOT NULL,
  `tip_materia` int NOT NULL,
  `num_materia` int NOT NULL,
  `ano_materia` int NOT NULL,
  `dat_materia` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `cod_materia` (`cod_materia`),
  KEY `tip_materia` (`tip_materia`),
  KEY `idx_numer_identificacao` (`tip_materia`,`num_materia`,`ano_materia`,`ind_excluido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `oradores` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `num_ordem` int NOT NULL,
  `url_discurso` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_num_ordem` (`cod_sessao_plen`,`num_ordem`,`ind_excluido`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `oradores_expediente` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `num_ordem` int NOT NULL,
  `url_discurso` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_num_ordem` (`cod_sessao_plen`,`num_ordem`,`ind_excluido`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `ordem_dia` (
  `cod_ordem` int NOT NULL AUTO_INCREMENT,
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
  `urgencia` int DEFAULT NULL,
  `tipo_discussao_ordem` int DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_ordem`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `cod_materia` (`cod_materia`),
  KEY `idx_dat_ordem` (`dat_ordem`),
  KEY `tip_votacao` (`tip_votacao`),
  KEY `tip_quorum` (`tip_quorum`),
  KEY `tip_turno` (`tip_turno`),
  KEY `num_ordem` (`num_ordem`),
  KEY `idx_cod_parecer` (`cod_parecer`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `ordem_dia_discussao` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_ordem` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `cod_ordem` (`cod_ordem`),
  KEY `cod_parlamentar` (`cod_parlamentar`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ordem_dia_presenca` (
  `cod_presenca_ordem_dia` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL DEFAULT '0',
  `cod_parlamentar` int NOT NULL,
  `tip_frequencia` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'P',
  `txt_justif_ausencia` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_ordem` date NOT NULL,
  `flag_presenca` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_presenca_ordem_dia`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `dat_ordem` (`dat_ordem`),
  KEY `tip_frequencia` (`tip_frequencia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `orgao` (
  `cod_orgao` int NOT NULL AUTO_INCREMENT,
  `nom_orgao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `sgl_orgao` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_unid_deliberativa` int NOT NULL DEFAULT '0',
  `end_orgao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tel_orgao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `end_email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_orgao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `origem` (
  `cod_origem` int NOT NULL AUTO_INCREMENT,
  `sgl_origem` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_origem` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_origem`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `parecer` (
  `cod_relatoria` int NOT NULL,
  `num_parecer` int DEFAULT NULL,
  `ano_parecer` int DEFAULT NULL,
  `cod_materia` int NOT NULL,
  `tip_conclusao` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_apresentacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_parecer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_relatoria`,`cod_materia`),
  KEY `idx_parecer_materia` (`cod_materia`,`ind_excluido`),
  KEY `cod_materia` (`cod_materia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `parlamentar` (
  `cod_parlamentar` int NOT NULL AUTO_INCREMENT,
  `nom_completo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_parlamentar` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_painel` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sex_parlamentar` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_nascimento` date DEFAULT NULL,
  `dat_falecimento` date DEFAULT NULL,
  `num_cpf` varchar(14) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_rg` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_tit_eleitor` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_situacao_militar` int DEFAULT NULL,
  `cod_nivel_instrucao` int DEFAULT NULL,
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
  `ind_ativo` int NOT NULL DEFAULT '0',
  `ind_unid_deliberativa` int DEFAULT NULL,
  `txt_biografia` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `texto_parlamentar` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_parlamentar`),
  KEY `cod_localidade_resid` (`cod_localidade_resid`),
  KEY `tip_situacao_militar` (`tip_situacao_militar`),
  KEY `cod_nivel_instrucao` (`cod_nivel_instrucao`),
  KEY `ind_parlamentar_ativo` (`ind_ativo`,`ind_excluido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `partido` (
  `cod_partido` int NOT NULL AUTO_INCREMENT,
  `sgl_partido` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nom_partido` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_criacao` date DEFAULT NULL,
  `dat_extincao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_partido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `periodo_comp_bancada` (
  `cod_periodo_comp` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `dat_inicio_periodo` date NOT NULL,
  `dat_fim_periodo` date NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_periodo_comp`),
  KEY `ind_percompbancada_datas` (`dat_inicio_periodo`,`dat_fim_periodo`,`ind_excluido`),
  KEY `idx_legislatura` (`num_legislatura`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `periodo_comp_comissao` (
  `cod_periodo_comp` int NOT NULL AUTO_INCREMENT,
  `dat_inicio_periodo` date NOT NULL,
  `dat_fim_periodo` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_periodo_comp`),
  KEY `ind_percompcom_datas` (`dat_inicio_periodo`,`dat_fim_periodo`,`ind_excluido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `periodo_comp_mesa` (
  `cod_periodo_comp` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `dat_inicio_periodo` date NOT NULL,
  `dat_fim_periodo` date NOT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_periodo_comp`),
  KEY `ind_percompmesa_datas` (`dat_inicio_periodo`,`dat_fim_periodo`,`ind_excluido`),
  KEY `idx_legislatura` (`num_legislatura`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `periodo_sessao` (
  `cod_periodo` int NOT NULL AUTO_INCREMENT,
  `num_periodo` int NOT NULL,
  `num_legislatura` int NOT NULL,
  `cod_sessao_leg` int NOT NULL,
  `tip_sessao` int NOT NULL,
  `dat_inicio` date NOT NULL,
  `dat_fim` date NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_periodo`),
  UNIQUE KEY `periodo` (`num_periodo`,`num_legislatura`,`cod_sessao_leg`,`tip_sessao`),
  KEY `idx_legislatura` (`num_legislatura`),
  KEY `idx_sessao_leg` (`cod_sessao_leg`),
  KEY `idx_tip_sessao` (`tip_sessao`),
  KEY `dat_incio` (`dat_inicio`),
  KEY `dat_fim` (`dat_fim`),
  KEY `num_periodo` (`num_periodo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `pessoa` (
  `cod_pessoa` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_pessoa`),
  KEY `num_cep` (`num_cep`),
  KEY `cod_logradouro` (`cod_logradouro`),
  KEY `nom_cidade` (`nom_cidade`),
  KEY `dat_nascimento` (`dat_nascimento`),
  KEY `des_profissao` (`des_profissao`),
  KEY `des_estado_civil` (`des_estado_civil`),
  KEY `sex_visitante` (`sex_pessoa`),
  KEY `nom_bairro` (`nom_bairro`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `peticao` (
  `cod_peticao` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_peticao`),
  KEY `cod_usuario` (`cod_usuario`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_documento` (`cod_documento`),
  KEY `cod_doc_acessorio` (`cod_doc_acessorio`),
  KEY `cod_norma` (`cod_norma`),
  KEY `num_protocolo` (`num_protocolo`),
  KEY `dat_envio` (`dat_envio`),
  KEY `dat_recebimento` (`dat_recebimento`),
  KEY `ind_excluido` (`ind_excluido`),
  KEY `num_norma` (`num_norma`),
  KEY `dat_norma` (`dat_norma`),
  KEY `tip_peticionamento` (`tip_peticionamento`) USING BTREE,
  KEY `cod_documento_vinculado` (`cod_documento_vinculado`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `proposicao` (
  `cod_proposicao` int NOT NULL AUTO_INCREMENT,
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
  `cod_revisor` int DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_proposicao`),
  KEY `tip_proposicao` (`tip_proposicao`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_emenda` (`cod_emenda`),
  KEY `cod_substitutivo` (`cod_substitutivo`),
  KEY `cod_autor` (`cod_autor`),
  KEY `idx_prop_autor` (`dat_envio`,`dat_recebimento`,`ind_excluido`),
  KEY `cod_parecer` (`cod_parecer`),
  KEY `cod_assunto` (`cod_assunto`),
  KEY `cod_assessor` (`cod_assessor`),
  KEY `cod_revisor` (`cod_revisor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `proposicao_geocode` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_proposicao` int NOT NULL,
  `endereco` varchar(300) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `lat` decimal(18,14) NOT NULL,
  `lng` decimal(18,13) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `cod_proposicao` (`cod_proposicao`),
  KEY `idx_cod_proposicao` (`cod_proposicao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `protocolo` (
  `cod_protocolo` int(7) UNSIGNED ZEROFILL NOT NULL AUTO_INCREMENT,
  `num_protocolo` int(7) UNSIGNED ZEROFILL DEFAULT NULL,
  `ano_protocolo` int NOT NULL,
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
  `tip_natureza_materia` int DEFAULT NULL,
  `cod_materia_principal` int DEFAULT NULL,
  `num_paginas` int DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_anulado` int NOT NULL DEFAULT '0',
  `txt_user_protocolo` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_user_anulacao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_ip_anulacao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_just_anulacao` varchar(400) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `timestamp_anulacao` datetime DEFAULT NULL,
  `codigo_acesso` varchar(18) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`cod_protocolo`),
  UNIQUE KEY `idx_num_protocolo` (`num_protocolo`,`ano_protocolo`),
  KEY `tip_protocolo` (`tip_protocolo`),
  KEY `cod_autor` (`cod_autor`),
  KEY `tip_materia` (`tip_materia`),
  KEY `tip_documento` (`tip_documento`),
  KEY `dat_protocolo` (`dat_protocolo`),
  KEY `ano_protocolo` (`ano_protocolo`),
  KEY `tip_processo` (`tip_processo`),
  KEY `codigo_acesso` (`codigo_acesso`),
  KEY `cod_materia_principal` (`cod_materia_principal`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `quorum_votacao` (
  `cod_quorum` int NOT NULL AUTO_INCREMENT,
  `des_quorum` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `txt_formula` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_quorum`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `regime_tramitacao` (
  `cod_regime_tramitacao` int NOT NULL AUTO_INCREMENT,
  `des_regime_tramitacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_regime_tramitacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `registro_votacao` (
  `cod_votacao` int NOT NULL AUTO_INCREMENT,
  `tip_resultado_votacao` int UNSIGNED NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_parecer` int DEFAULT NULL,
  `cod_ordem` int NOT NULL,
  `cod_emenda` int DEFAULT NULL,
  `cod_subemenda` int DEFAULT NULL,
  `cod_substitutivo` int DEFAULT NULL,
  `num_votos_sim` int UNSIGNED NOT NULL,
  `num_votos_nao` int UNSIGNED NOT NULL,
  `num_abstencao` int UNSIGNED NOT NULL,
  `num_ausentes` int UNSIGNED DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_obs_anterior` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int UNSIGNED NOT NULL,
  PRIMARY KEY (`cod_votacao`),
  UNIQUE KEY `idx_unique` (`cod_materia`,`cod_ordem`,`cod_emenda`,`cod_substitutivo`) USING BTREE,
  KEY `cod_ordem` (`cod_ordem`),
  KEY `cod_materia` (`cod_materia`),
  KEY `tip_resultado_votacao` (`tip_resultado_votacao`),
  KEY `cod_emenda` (`cod_emenda`),
  KEY `cod_subemenda` (`cod_subemenda`),
  KEY `cod_substitutivo` (`cod_substitutivo`),
  KEY `cod_parecer` (`cod_parecer`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `registro_votacao_parlamentar` (
  `cod_votacao` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `vot_parlamentar` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int UNSIGNED NOT NULL,
  PRIMARY KEY (`cod_votacao`,`cod_parlamentar`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_votacao` (`cod_votacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `relatoria` (
  `cod_relatoria` int NOT NULL AUTO_INCREMENT,
  `cod_materia` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `tip_fim_relatoria` int DEFAULT NULL,
  `cod_comissao` int DEFAULT NULL,
  `num_ordem` int NOT NULL,
  `dat_desig_relator` date NOT NULL,
  `dat_destit_relator` datetime DEFAULT NULL,
  `tip_apresentacao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_parecer` int DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `ano_parecer` int DEFAULT NULL,
  `txt_parecer` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `tip_conclusao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_relatoria`),
  KEY `cod_comissao` (`cod_comissao`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `tip_fim_relatoria` (`tip_fim_relatoria`),
  KEY `idx_relat_materia` (`cod_materia`,`cod_parlamentar`,`ind_excluido`),
  KEY `num_protocolo` (`num_protocolo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `reuniao_comissao` (
  `cod_reuniao` int NOT NULL AUTO_INCREMENT,
  `cod_comissao` int NOT NULL,
  `num_reuniao` int NOT NULL,
  `des_tipo_reuniao` varchar(15) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_tema` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_inicio_reuniao` date NOT NULL,
  `hr_inicio_reuniao` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hr_fim_reuniao` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `url_video` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_reuniao`),
  KEY `cod_comissao` (`cod_comissao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `reuniao_comissao_pauta` (
  `cod_item` int NOT NULL AUTO_INCREMENT,
  `cod_reuniao` int NOT NULL,
  `num_ordem` int NOT NULL,
  `cod_materia` int DEFAULT NULL,
  `cod_emenda` int DEFAULT NULL,
  `cod_substitutivo` int DEFAULT NULL,
  `cod_parecer` int DEFAULT NULL,
  `cod_relator` int DEFAULT NULL,
  `tip_resultado_votacao` int UNSIGNED DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_item`),
  KEY `cod_reuniao` (`cod_reuniao`),
  KEY `cod_materia` (`cod_materia`),
  KEY `cod_emenda` (`cod_emenda`),
  KEY `cod_substitutivo` (`cod_substitutivo`),
  KEY `cod_parecer` (`cod_parecer`),
  KEY `cod_relator` (`cod_relator`),
  KEY `tip_resultado_votacao` (`tip_resultado_votacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `reuniao_comissao_presenca` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_reuniao` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_reuniao_parlamentar` (`cod_reuniao`,`cod_parlamentar`) USING BTREE,
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `cod_reuniao` (`cod_reuniao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sessao_legislativa` (
  `cod_sessao_leg` int NOT NULL AUTO_INCREMENT,
  `num_legislatura` int NOT NULL,
  `num_sessao_leg` int NOT NULL,
  `tip_sessao_leg` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_inicio` date NOT NULL,
  `dat_fim` date NOT NULL,
  `dat_inicio_intervalo` date DEFAULT NULL,
  `dat_fim_intervalo` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_sessao_leg`),
  KEY `idx_sessleg_datas` (`dat_inicio`,`ind_excluido`,`dat_fim`,`dat_inicio_intervalo`,`dat_fim_intervalo`),
  KEY `idx_sessleg_legislatura` (`num_legislatura`,`ind_excluido`),
  KEY `idx_legislatura` (`num_legislatura`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `sessao_plenaria` (
  `cod_sessao_plen` int NOT NULL AUTO_INCREMENT,
  `cod_andamento_sessao` int DEFAULT NULL,
  `tip_sessao` int NOT NULL,
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
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_sessao_plen`),
  KEY `cod_sessao_leg` (`cod_sessao_leg`),
  KEY `tip_sessao` (`tip_sessao`),
  KEY `num_legislatura` (`num_legislatura`),
  KEY `dat_inicio_sessao` (`dat_inicio_sessao`),
  KEY `num_sessao_plen` (`num_sessao_plen`),
  KEY `cod_periodo_sessao` (`cod_periodo_sessao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `sessao_plenaria_painel` (
  `cod_item` int NOT NULL AUTO_INCREMENT,
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
  `ind_extrapauta` int DEFAULT '0',
  `ind_exibicao` int DEFAULT '0',
  PRIMARY KEY (`cod_item`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sessao_plenaria_presenca` (
  `cod_presenca_sessao` int NOT NULL AUTO_INCREMENT,
  `cod_sessao_plen` int NOT NULL,
  `cod_parlamentar` int NOT NULL,
  `tip_frequencia` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'P',
  `txt_justif_ausencia` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_sessao` date DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_presenca_sessao`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `idx_sessao_parlamentar` (`cod_sessao_plen`,`cod_parlamentar`),
  KEY `cod_sessao_plen` (`cod_sessao_plen`),
  KEY `dat_sessao` (`dat_sessao`),
  KEY `tip_frequencia` (`tip_frequencia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `status_tramitacao` (
  `cod_status` int NOT NULL AUTO_INCREMENT,
  `sgl_status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_status` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_fim_tramitacao` int NOT NULL DEFAULT '0',
  `ind_retorno_tramitacao` int NOT NULL DEFAULT '0',
  `num_dias_prazo` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_status`),
  KEY `sgl_status` (`sgl_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `status_tramitacao_administrativo` (
  `cod_status` int NOT NULL AUTO_INCREMENT,
  `sgl_status` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_status` varchar(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_fim_tramitacao` int NOT NULL DEFAULT '0',
  `ind_retorno_tramitacao` int NOT NULL DEFAULT '0',
  `num_dias_prazo` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_status`),
  KEY `sgl_status` (`sgl_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `substitutivo` (
  `cod_substitutivo` int NOT NULL AUTO_INCREMENT,
  `num_substitutivo` int NOT NULL,
  `cod_materia` int NOT NULL,
  `cod_autor` int DEFAULT NULL,
  `num_protocolo` int DEFAULT NULL,
  `dat_apresentacao` date DEFAULT NULL,
  `txt_ementa` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_substitutivo`),
  KEY `idx_cod_materia` (`cod_materia`),
  KEY `idx_substitutivo` (`cod_substitutivo`,`cod_materia`) USING BTREE,
  KEY `cod_autor` (`cod_autor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_afastamento` (
  `tip_afastamento` int NOT NULL AUTO_INCREMENT,
  `des_afastamento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_afastamento` int NOT NULL,
  `ind_fim_mandato` int NOT NULL,
  `des_dispositivo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_afastamento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_autor` (
  `tip_autor` int NOT NULL,
  `des_tipo_autor` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_proposicao` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_autor`),
  KEY `des_tipo_autor` (`des_tipo_autor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_comissao` (
  `tip_comissao` int NOT NULL AUTO_INCREMENT,
  `nom_tipo_comissao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_natureza_comissao` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_tipo_comissao` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_dispositivo_regimental` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_comissao`),
  KEY `nom_tipo_comissao` (`nom_tipo_comissao`),
  KEY `sgl_natureza_comissao` (`sgl_natureza_comissao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_dependente` (
  `tip_dependente` int NOT NULL AUTO_INCREMENT,
  `des_tipo_dependente` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_dependente`),
  KEY `des_tipo_dependente` (`des_tipo_dependente`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_documento` (
  `tip_documento` int NOT NULL AUTO_INCREMENT,
  `des_tipo_documento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_documento`),
  KEY `des_tipo_documento` (`des_tipo_documento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_documento_administrativo` (
  `tip_documento` int NOT NULL AUTO_INCREMENT,
  `sgl_tipo_documento` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tipo_documento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_natureza` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'P',
  `ind_publico` int NOT NULL DEFAULT '0',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`tip_documento`),
  KEY `des_tipo_documento` (`des_tipo_documento`),
  KEY `ind_publico` (`ind_publico`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `tipo_emenda` (
  `tip_emenda` int NOT NULL AUTO_INCREMENT,
  `des_tipo_emenda` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_emenda`),
  KEY `des_tipo_emenda` (`des_tipo_emenda`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_expediente` (
  `cod_expediente` int NOT NULL AUTO_INCREMENT,
  `nom_expediente` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ordem` int DEFAULT NULL,
  `ind_excluido` int UNSIGNED NOT NULL,
  PRIMARY KEY (`cod_expediente`),
  KEY `nom_expediente` (`nom_expediente`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_fim_relatoria` (
  `tip_fim_relatoria` int NOT NULL AUTO_INCREMENT,
  `des_fim_relatoria` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_fim_relatoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_instituicao` (
  `tip_instituicao` int NOT NULL AUTO_INCREMENT,
  `nom_tipo_instituicao` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`tip_instituicao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_materia_legislativa` (
  `tip_materia` int NOT NULL AUTO_INCREMENT,
  `sgl_tipo_materia` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tipo_materia` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_natureza` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_publico` int NOT NULL DEFAULT '1',
  `ind_num_automatica` int NOT NULL DEFAULT '0',
  `quorum_minimo_votacao` int NOT NULL DEFAULT '1',
  `ordem` int DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_materia`),
  KEY `des_tipo_materia` (`des_tipo_materia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_norma_juridica` (
  `tip_norma` int NOT NULL AUTO_INCREMENT,
  `voc_lexml` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sgl_tipo_norma` char(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `des_tipo_norma` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_norma`),
  KEY `des_tipo_norma` (`des_tipo_norma`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_peticionamento` (
  `tip_peticionamento` int NOT NULL AUTO_INCREMENT,
  `des_tipo_peticionamento` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_norma` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_doc_adm` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_doc_materia` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_derivado` int NOT NULL,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_peticionamento`),
  KEY `cod_unid_tram_dest` (`cod_unid_tram_dest`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_proposicao` (
  `tip_proposicao` int NOT NULL AUTO_INCREMENT,
  `des_tipo_proposicao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_mat_ou_doc` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tip_mat_ou_doc` int NOT NULL,
  `nom_modelo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_proposicao`),
  KEY `des_tipo_proposicao` (`des_tipo_proposicao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_resultado_votacao` (
  `tip_resultado_votacao` int UNSIGNED NOT NULL AUTO_INCREMENT,
  `nom_resultado` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int UNSIGNED NOT NULL,
  PRIMARY KEY (`tip_resultado_votacao`),
  KEY `nom_resultado` (`nom_resultado`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_sessao_plenaria` (
  `tip_sessao` int NOT NULL AUTO_INCREMENT,
  `nom_sessao` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `num_minimo` int NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_sessao`),
  KEY `nom_sessao` (`nom_sessao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tipo_situacao_materia` (
  `tip_situacao_materia` int NOT NULL AUTO_INCREMENT,
  `des_tipo_situacao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`tip_situacao_materia`),
  KEY `des_tipo_situacao` (`des_tipo_situacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_situacao_militar` (
  `tip_situacao_militar` int NOT NULL,
  `des_tipo_situacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_situacao_militar`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_situacao_norma` (
  `tip_situacao_norma` int NOT NULL AUTO_INCREMENT,
  `des_tipo_situacao` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`tip_situacao_norma`),
  KEY `des_tipo_situacao` (`des_tipo_situacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_vinculo_norma` (
  `cod_tip_vinculo` int NOT NULL AUTO_INCREMENT,
  `tipo_vinculo` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_vinculo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `des_vinculo_passivo` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `tip_situacao` int DEFAULT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_tip_vinculo`),
  UNIQUE KEY `tipo_vinculo` (`tipo_vinculo`),
  UNIQUE KEY `idx_vinculo` (`tipo_vinculo`,`des_vinculo`,`des_vinculo_passivo`,`ind_excluido`),
  KEY `tip_situacao` (`tip_situacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tipo_votacao` (
  `tip_votacao` int NOT NULL AUTO_INCREMENT,
  `des_tipo_votacao` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`tip_votacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tramitacao` (
  `cod_tramitacao` int NOT NULL AUTO_INCREMENT,
  `cod_status` int DEFAULT NULL,
  `cod_materia` int NOT NULL,
  `dat_tramitacao` datetime DEFAULT NULL,
  `cod_unid_tram_local` int DEFAULT NULL,
  `cod_usuario_local` int DEFAULT NULL,
  `dat_encaminha` datetime DEFAULT NULL,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `cod_usuario_dest` int DEFAULT NULL,
  `dat_recebimento` datetime DEFAULT NULL,
  `ind_ult_tramitacao` int NOT NULL DEFAULT '0',
  `ind_urgencia` int NOT NULL,
  `sgl_turno` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_tramitacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_fim_prazo` date DEFAULT NULL,
  `dat_visualizacao` datetime DEFAULT NULL,
  `cod_usuario_visualiza` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_tramitacao`),
  KEY `cod_unid_tram_local` (`cod_unid_tram_local`),
  KEY `cod_unid_tram_dest` (`cod_unid_tram_dest`),
  KEY `cod_status` (`cod_status`),
  KEY `cod_materia` (`cod_materia`),
  KEY `idx_tramit_ultmat` (`ind_ult_tramitacao`,`dat_tramitacao`,`cod_materia`,`ind_excluido`),
  KEY `sgl_turno` (`sgl_turno`),
  KEY `cod_usuario_local` (`cod_usuario_local`),
  KEY `cod_usuario_dest` (`cod_usuario_dest`),
  KEY `cod_usuario_visualiza` (`cod_usuario_visualiza`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `tramitacao_administrativo` (
  `cod_tramitacao` int NOT NULL AUTO_INCREMENT,
  `cod_documento` int NOT NULL,
  `dat_tramitacao` datetime DEFAULT NULL,
  `cod_unid_tram_local` int DEFAULT NULL,
  `cod_usuario_local` int DEFAULT NULL,
  `dat_encaminha` datetime DEFAULT NULL,
  `cod_unid_tram_dest` int DEFAULT NULL,
  `cod_usuario_dest` int DEFAULT NULL,
  `dat_recebimento` datetime DEFAULT NULL,
  `cod_status` int DEFAULT NULL,
  `ind_ult_tramitacao` int NOT NULL DEFAULT '0',
  `txt_tramitacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `dat_fim_prazo` date DEFAULT NULL,
  `dat_visualizacao` datetime DEFAULT NULL,
  `cod_usuario_visualiza` int DEFAULT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_tramitacao`),
  KEY `cod_unid_tram_dest` (`cod_unid_tram_dest`),
  KEY `tramitacao_ind1` (`ind_ult_tramitacao`),
  KEY `cod_unid_tram_local` (`cod_unid_tram_local`),
  KEY `cod_status` (`cod_status`),
  KEY `cod_documento` (`cod_documento`),
  KEY `cod_usuario_local` (`cod_usuario_local`),
  KEY `cod_usuario_dest` (`cod_usuario_dest`),
  KEY `cod_usuario_visualiza` (`cod_usuario_visualiza`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=1;

CREATE TABLE IF NOT EXISTS `turno_discussao` (
  `cod_turno` int NOT NULL AUTO_INCREMENT,
  `sgl_turno` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'S',
  `des_turno` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_turno`),
  UNIQUE KEY `idx_unique_key` (`cod_turno`,`sgl_turno`,`ind_excluido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `unidade_tramitacao` (
  `cod_unid_tramitacao` int NOT NULL AUTO_INCREMENT,
  `cod_comissao` int DEFAULT NULL,
  `cod_orgao` int DEFAULT NULL,
  `cod_parlamentar` int DEFAULT NULL,
  `ind_leg` int DEFAULT '0',
  `unid_dest_permitidas` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `status_permitidos` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_adm` int DEFAULT '0',
  `status_adm_permitidos` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_unid_tramitacao`),
  KEY `idx_unidtramit_orgao` (`cod_orgao`,`ind_excluido`),
  KEY `idx_unidtramit_comissao` (`cod_comissao`,`ind_excluido`),
  KEY `cod_orgao` (`cod_orgao`),
  KEY `cod_comissao` (`cod_comissao`),
  KEY `idx_unidtramit_parlamentar` (`cod_parlamentar`,`ind_excluido`),
  KEY `cod_parlamentar` (`cod_parlamentar`),
  KEY `ind_leg` (`ind_leg`),
  KEY `ind_adm` (`ind_adm`),
  KEY `ind_leg_2` (`ind_leg`),
  KEY `ind_adm_2` (`ind_adm`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `usuario` (
  `cod_usuario` int NOT NULL AUTO_INCREMENT,
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
  `ind_excluido` int NOT NULL,
  PRIMARY KEY (`cod_usuario`),
  KEY `idx_col_username` (`col_username`),
  KEY `idx_cod_localidade` (`cod_localidade_resid`),
  KEY `ind_ativo` (`ind_ativo`),
  KEY `ind_interno` (`ind_interno`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `usuario_peticionamento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_usuario` int NOT NULL,
  `tip_peticionamento` int NOT NULL,
  `ind_excluido` tinyint NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_usuario` (`cod_usuario`),
  KEY `idx_tip_peticionamento` (`tip_peticionamento`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `usuario_tipo_documento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_usuario` int NOT NULL,
  `tip_documento` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_usuario` (`cod_usuario`),
  KEY `idx_tip_documento` (`tip_documento`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `usuario_unid_tram` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_usuario` int NOT NULL,
  `cod_unid_tramitacao` int NOT NULL,
  `ind_responsavel` int NOT NULL DEFAULT '0',
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_usuario` (`cod_usuario`),
  KEY `idx_unid_tramitacao` (`cod_unid_tramitacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `vinculo_norma_juridica` (
  `cod_vinculo` int NOT NULL AUTO_INCREMENT,
  `cod_norma_referente` int NOT NULL,
  `cod_norma_referida` int DEFAULT NULL,
  `tip_vinculo` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `txt_observacao_vinculo` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ind_excluido` int DEFAULT '0',
  PRIMARY KEY (`cod_vinculo`),
  KEY `tip_vinculo` (`tip_vinculo`),
  KEY `idx_vnj_norma_referente` (`cod_norma_referente`,`cod_norma_referida`,`ind_excluido`),
  KEY `idx_vnj_norma_referida` (`cod_norma_referida`,`cod_norma_referente`,`ind_excluido`),
  KEY `cod_norma_referente` (`cod_norma_referente`),
  KEY `cod_norma_referida` (`cod_norma_referida`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci PACK_KEYS=0;

CREATE TABLE IF NOT EXISTS `visita` (
  `cod_visita` int NOT NULL AUTO_INCREMENT,
  `cod_pessoa` int NOT NULL,
  `dat_entrada` datetime NOT NULL,
  `cod_funcionario` int NOT NULL,
  `num_cracha` int DEFAULT NULL,
  `dat_saida` datetime DEFAULT NULL,
  `txt_atendimento` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `des_situacao` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dat_solucao` date DEFAULT NULL,
  `txt_observacao` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`cod_visita`),
  KEY `cod_funcionario` (`cod_funcionario`),
  KEY `cod_pessoa` (`cod_pessoa`) USING BTREE,
  KEY `dat_entrada` (`dat_entrada`),
  KEY `des_situacao` (`des_situacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


ALTER TABLE `autor` ADD FULLTEXT KEY `nom_autor` (`nom_autor`);

ALTER TABLE `bancada` ADD FULLTEXT KEY `nom_bancada` (`nom_bancada`);

ALTER TABLE `comissao` ADD FULLTEXT KEY `nom_comissao` (`nom_comissao`);

ALTER TABLE `documento_acessorio` ADD FULLTEXT KEY `idx_ementa` (`txt_ementa`);

ALTER TABLE `documento_acessorio_administrativo` ADD FULLTEXT KEY `idx_assunto` (`txt_assunto`);

ALTER TABLE `documento_administrativo` ADD FULLTEXT KEY `idx_busca_documento` (`txt_assunto`,`txt_observacao`);
ALTER TABLE `documento_administrativo` ADD FULLTEXT KEY `txt_interessado` (`txt_interessado`);

ALTER TABLE `documento_comissao` ADD FULLTEXT KEY `txt_descricao` (`txt_descricao`);

ALTER TABLE `emenda` ADD FULLTEXT KEY `idx_txt_ementa` (`txt_ementa`);

ALTER TABLE `gabinete_atendimento` ADD FULLTEXT KEY `idx_assunto` (`txt_assunto`);

ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `nom_eleitor` (`nom_eleitor`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `des_profissao` (`des_profissao`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `end_residencial` (`end_residencial`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `nom_localidade` (`nom_localidade`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `des_local_trabalho` (`des_local_trabalho`);
ALTER TABLE `gabinete_eleitor` ADD FULLTEXT KEY `nom_bairro` (`nom_bairro`);

ALTER TABLE `instituicao` ADD FULLTEXT KEY `idx_nom_instituicao` (`nom_instituicao`);
ALTER TABLE `instituicao` ADD FULLTEXT KEY `idx_nom_responsavel` (`nom_responsavel`);

ALTER TABLE `localidade` ADD FULLTEXT KEY `nom_localidade_pesq` (`nom_localidade_pesq`);

ALTER TABLE `logradouro` ADD FULLTEXT KEY `nom_logradouro` (`nom_logradouro`);

ALTER TABLE `materia_legislativa` ADD FULLTEXT KEY `idx_busca` (`txt_ementa`,`txt_observacao`,`txt_indexacao`);

ALTER TABLE `norma_juridica` ADD FULLTEXT KEY `idx_busca` (`txt_ementa`,`txt_observacao`,`txt_indexacao`);

ALTER TABLE `parlamentar` ADD FULLTEXT KEY `nom_completo` (`nom_completo`);
ALTER TABLE `parlamentar` ADD FULLTEXT KEY `nom_parlamentar` (`nom_parlamentar`);

ALTER TABLE `pessoa` ADD FULLTEXT KEY `nom_pessoa` (`nom_pessoa`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `nom_conjuge` (`nom_conjuge`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `idx_busca` (`doc_identidade`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `end_residencial` (`end_residencial`);
ALTER TABLE `pessoa` ADD FULLTEXT KEY `doc_identidade` (`doc_identidade`);

ALTER TABLE `protocolo` ADD FULLTEXT KEY `idx_busca_protocolo` (`txt_assunto_ementa`,`txt_observacao`);
ALTER TABLE `protocolo` ADD FULLTEXT KEY `txt_interessado` (`txt_interessado`);

ALTER TABLE `status_tramitacao` ADD FULLTEXT KEY `des_status` (`des_status`);

ALTER TABLE `status_tramitacao_administrativo` ADD FULLTEXT KEY `des_status` (`des_status`);

ALTER TABLE `substitutivo` ADD FULLTEXT KEY `idx_txt_ementa` (`txt_ementa`);
ALTER TABLE `substitutivo` ADD FULLTEXT KEY `txt_observacao` (`txt_observacao`);


ALTER TABLE `afastamento`
  ADD CONSTRAINT `afastamento_ibfk_1` FOREIGN KEY (`cod_mandato`) REFERENCES `mandato` (`cod_mandato`) ON DELETE CASCADE ON UPDATE RESTRICT,
  ADD CONSTRAINT `afastamento_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE,
  ADD CONSTRAINT `afastamento_ibfk_5` FOREIGN KEY (`tip_afastamento`) REFERENCES `tipo_afastamento` (`tip_afastamento`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `afastamento_ibfk_6` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `anexada`
  ADD CONSTRAINT `anexada_ibfk_1` FOREIGN KEY (`cod_materia_anexada`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `anexada_ibfk_2` FOREIGN KEY (`cod_materia_principal`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

ALTER TABLE `anexo_norma`
  ADD CONSTRAINT `anexo_norma_ibfk_1` FOREIGN KEY (`cod_norma`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

ALTER TABLE `assessor_parlamentar`
  ADD CONSTRAINT `assessor_parlamentar_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE;

ALTER TABLE `assinatura_documento`
  ADD CONSTRAINT `assinatura_documento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `assinatura_documento_ibfk_2` FOREIGN KEY (`cod_solicitante`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `assunto_proposicao`
  ADD CONSTRAINT `assunto_proposicao_ibfk_1` FOREIGN KEY (`tip_proposicao`) REFERENCES `tipo_proposicao` (`tip_proposicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `autor`
  ADD CONSTRAINT `autor_ibfk_1` FOREIGN KEY (`cod_bancada`) REFERENCES `bancada` (`cod_bancada`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_2` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_3` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_4` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autor_ibfk_5` FOREIGN KEY (`tip_autor`) REFERENCES `tipo_autor` (`tip_autor`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `autoria`
  ADD CONSTRAINT `autoria_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `autoria_ibfk_2` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `autoria_emenda`
  ADD CONSTRAINT `autoria_emenda_ibfk_1` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autoria_emenda_ibfk_2` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE CASCADE;

ALTER TABLE `autoria_substitutivo`
  ADD CONSTRAINT `autoria_substitutivo_ibfk_1` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `autoria_substitutivo_ibfk_2` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE CASCADE;

ALTER TABLE `bancada`
  ADD CONSTRAINT `bancada_ibfk_1` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT,
  ADD CONSTRAINT `bancada_ibfk_2` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `coligacao`
  ADD CONSTRAINT `coligacao_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `comissao`
  ADD CONSTRAINT `comissao_ibfk_1` FOREIGN KEY (`tip_comissao`) REFERENCES `tipo_comissao` (`tip_comissao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `composicao_bancada`
  ADD CONSTRAINT `composicao_bancada_ibfk_1` FOREIGN KEY (`cod_bancada`) REFERENCES `bancada` (`cod_bancada`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_bancada_ibfk_3` FOREIGN KEY (`cod_periodo_comp`) REFERENCES `periodo_comp_bancada` (`cod_periodo_comp`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_bancada_ibfk_4` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_bancada_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_bancada` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `composicao_coligacao`
  ADD CONSTRAINT `composicao_coligacao_ibfk_1` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT;

ALTER TABLE `composicao_comissao`
  ADD CONSTRAINT `composicao_comissao_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`),
  ADD CONSTRAINT `composicao_comissao_ibfk_3` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `composicao_comissao_ibfk_4` FOREIGN KEY (`cod_periodo_comp`) REFERENCES `periodo_comp_comissao` (`cod_periodo_comp`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_comissao_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_comissao` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `composicao_executivo`
  ADD CONSTRAINT `composicao_executivo_ibfk_2` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_executivo` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `composicao_executivo_ibfk_3` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `composicao_executivo_ibfk_4` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `composicao_mesa`
  ADD CONSTRAINT `composicao_mesa_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_mesa_ibfk_3` FOREIGN KEY (`cod_periodo_comp`) REFERENCES `periodo_comp_mesa` (`cod_periodo_comp`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_mesa_ibfk_4` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT,
  ADD CONSTRAINT `composicao_mesa_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_mesa` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `dependente`
  ADD CONSTRAINT `dependente_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `dependente_ibfk_2` FOREIGN KEY (`tip_dependente`) REFERENCES `tipo_dependente` (`tip_dependente`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `despacho_inicial`
  ADD CONSTRAINT `despacho_inicial_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `despacho_inicial_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

ALTER TABLE `destinatario_oficio`
  ADD CONSTRAINT `destinatario_oficio_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `destinatario_oficio_ibfk_2` FOREIGN KEY (`cod_instituicao`) REFERENCES `instituicao` (`cod_instituicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `documento_acessorio`
  ADD CONSTRAINT `documento_acessorio_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `documento_acessorio_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento` (`tip_documento`) ON DELETE RESTRICT;

ALTER TABLE `documento_acessorio_administrativo`
  ADD CONSTRAINT `documento_acessorio_administrativo_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `documento_acessorio_administrativo_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT;

ALTER TABLE `documento_administrativo`
  ADD CONSTRAINT `documento_administrativo_ibfk_1` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT;

ALTER TABLE `documento_administrativo_materia`
  ADD CONSTRAINT `documento_administrativo_materia_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE,
  ADD CONSTRAINT `documento_administrativo_materia_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

ALTER TABLE `documento_administrativo_vinculado`
  ADD CONSTRAINT `documento_administrativo_vinculado_ibfk_1` FOREIGN KEY (`cod_documento_vinculado`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE,
  ADD CONSTRAINT `documento_administrativo_vinculado_ibfk_2` FOREIGN KEY (`cod_documento_vinculante`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE;

ALTER TABLE `documento_comissao`
  ADD CONSTRAINT `documento_comissao_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT;

ALTER TABLE `emenda`
  ADD CONSTRAINT `emenda_ibfk_1` FOREIGN KEY (`tip_emenda`) REFERENCES `tipo_emenda` (`tip_emenda`) ON DELETE RESTRICT,
  ADD CONSTRAINT `emenda_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

ALTER TABLE `encerramento_presenca`
  ADD CONSTRAINT `encerramento_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `encerramento_presenca_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE;

ALTER TABLE `expediente_discussao`
  ADD CONSTRAINT `expediente_discussao_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `fk_cod_ordem` FOREIGN KEY (`cod_ordem`) REFERENCES `expediente_materia` (`cod_ordem`) ON DELETE CASCADE;

ALTER TABLE `expediente_materia`
  ADD CONSTRAINT `expediente_materia_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_2` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_3` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `expediente_materia_ibfk_4` FOREIGN KEY (`tip_quorum`) REFERENCES `quorum_votacao` (`cod_quorum`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_5` FOREIGN KEY (`tip_votacao`) REFERENCES `tipo_votacao` (`tip_votacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_materia_ibfk_6` FOREIGN KEY (`tip_turno`) REFERENCES `turno_discussao` (`cod_turno`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `expediente_presenca`
  ADD CONSTRAINT `expediente_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `expediente_presenca_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE;

ALTER TABLE `expediente_sessao_plenaria`
  ADD CONSTRAINT `expediente_sessao_plenaria_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `expediente_sessao_plenaria_ibfk_2` FOREIGN KEY (`cod_expediente`) REFERENCES `tipo_expediente` (`cod_expediente`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `filiacao`
  ADD CONSTRAINT `filiacao_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `filiacao_ibfk_2` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT;

ALTER TABLE `funcionario`
  ADD CONSTRAINT `funcionario_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT;

ALTER TABLE `gabinete_atendimento`
  ADD CONSTRAINT `gabinete_atendimento_ibfk_1` FOREIGN KEY (`cod_eleitor`) REFERENCES `gabinete_eleitor` (`cod_eleitor`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `gabinete_atendimento_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE `gabinete_eleitor`
  ADD CONSTRAINT `gabinete_eleitor_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `gabinete_eleitor_ibfk_2` FOREIGN KEY (`cod_assessor`) REFERENCES `assessor_parlamentar` (`cod_assessor`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `instituicao`
  ADD CONSTRAINT `instituicao_ibfk_2` FOREIGN KEY (`tip_instituicao`) REFERENCES `tipo_instituicao` (`tip_instituicao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `instituicao_ibfk_3` FOREIGN KEY (`cod_localidade`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT;

ALTER TABLE `legislacao_citada`
  ADD CONSTRAINT `legislacao_citada_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `legislacao_citada_ibfk_2` FOREIGN KEY (`cod_norma`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

ALTER TABLE `liderancas_partidarias`
  ADD CONSTRAINT `liderancas_partidarias_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `liderancas_partidarias_ibfk_2` FOREIGN KEY (`cod_partido`) REFERENCES `partido` (`cod_partido`) ON DELETE RESTRICT,
  ADD CONSTRAINT `liderancas_partidarias_ibfk_3` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT;

ALTER TABLE `logradouro`
  ADD CONSTRAINT `logradouro_ibfk_1` FOREIGN KEY (`cod_localidade`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT,
  ADD CONSTRAINT `logradouro_ibfk_2` FOREIGN KEY (`cod_norma`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

ALTER TABLE `mandato`
  ADD CONSTRAINT `mandato_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE CASCADE,
  ADD CONSTRAINT `mandato_ibfk_3` FOREIGN KEY (`cod_coligacao`) REFERENCES `coligacao` (`cod_coligacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `mandato_ibfk_4` FOREIGN KEY (`tip_afastamento`) REFERENCES `tipo_afastamento` (`tip_afastamento`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mandato_ibfk_5` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `materia_apresentada_sessao`
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_2` FOREIGN KEY (`cod_doc_acessorio`) REFERENCES `documento_acessorio` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_3` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_4` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_5` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_6` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_apresentada_sessao_ibfk_7` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE RESTRICT;

ALTER TABLE `materia_legislativa`
  ADD CONSTRAINT `materia_legislativa_ibfk_2` FOREIGN KEY (`cod_local_origem_externa`) REFERENCES `origem` (`cod_origem`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_legislativa_ibfk_3` FOREIGN KEY (`tip_quorum`) REFERENCES `quorum_votacao` (`cod_quorum`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_legislativa_ibfk_5` FOREIGN KEY (`tip_id_basica`) REFERENCES `tipo_materia_legislativa` (`tip_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `materia_legislativa_ibfk_6` FOREIGN KEY (`cod_regime_tramitacao`) REFERENCES `regime_tramitacao` (`cod_regime_tramitacao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `mesa_sessao_plenaria`
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_3` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_4` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `mesa_sessao_plenaria_ibfk_5` FOREIGN KEY (`cod_cargo`) REFERENCES `cargo_mesa` (`cod_cargo`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `norma_juridica`
  ADD CONSTRAINT `norma_juridica_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE SET NULL,
  ADD CONSTRAINT `norma_juridica_ibfk_2` FOREIGN KEY (`cod_situacao`) REFERENCES `tipo_situacao_norma` (`tip_situacao_norma`) ON DELETE SET NULL ON UPDATE RESTRICT,
  ADD CONSTRAINT `norma_juridica_ibfk_3` FOREIGN KEY (`tip_norma`) REFERENCES `tipo_norma_juridica` (`tip_norma`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `numeracao`
  ADD CONSTRAINT `numeracao_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `numeracao_ibfk_2` FOREIGN KEY (`tip_materia`) REFERENCES `tipo_materia_legislativa` (`tip_materia`) ON DELETE CASCADE;

ALTER TABLE `oradores`
  ADD CONSTRAINT `oradores_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `oradores_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

ALTER TABLE `oradores_expediente`
  ADD CONSTRAINT `oradores_expediente_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `oradores_expediente_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

ALTER TABLE `ordem_dia`
  ADD CONSTRAINT `ordem_dia_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `ordem_dia_ibfk_3` FOREIGN KEY (`tip_quorum`) REFERENCES `quorum_votacao` (`cod_quorum`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_4` FOREIGN KEY (`tip_votacao`) REFERENCES `tipo_votacao` (`tip_votacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_5` FOREIGN KEY (`tip_turno`) REFERENCES `turno_discussao` (`cod_turno`) ON DELETE RESTRICT,
  ADD CONSTRAINT `ordem_dia_ibfk_6` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `ordem_dia_discussao`
  ADD CONSTRAINT `ordem_dia_discussao_ibfk_1` FOREIGN KEY (`cod_ordem`) REFERENCES `ordem_dia` (`cod_ordem`) ON DELETE CASCADE,
  ADD CONSTRAINT `ordem_dia_discussao_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

ALTER TABLE `ordem_dia_presenca`
  ADD CONSTRAINT `ordem_dia_presenca_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE,
  ADD CONSTRAINT `ordem_dia_presenca_ibfk_2` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

ALTER TABLE `parecer`
  ADD CONSTRAINT `parecer_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `parecer_ibfk_2` FOREIGN KEY (`cod_relatoria`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE CASCADE;

ALTER TABLE `parlamentar`
  ADD CONSTRAINT `parlamentar_ibfk_1` FOREIGN KEY (`cod_localidade_resid`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT,
  ADD CONSTRAINT `parlamentar_ibfk_4` FOREIGN KEY (`cod_nivel_instrucao`) REFERENCES `nivel_instrucao` (`cod_nivel_instrucao`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `parlamentar_ibfk_5` FOREIGN KEY (`tip_situacao_militar`) REFERENCES `tipo_situacao_militar` (`tip_situacao_militar`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `periodo_comp_bancada`
  ADD CONSTRAINT `periodo_comp_bancada_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `periodo_comp_mesa`
  ADD CONSTRAINT `periodo_comp_mesa_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `periodo_sessao`
  ADD CONSTRAINT `periodo_sessao_ibfk_1` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `periodo_sessao_ibfk_2` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `periodo_sessao_ibfk_3` FOREIGN KEY (`tip_sessao`) REFERENCES `tipo_sessao_plenaria` (`tip_sessao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `peticao`
  ADD CONSTRAINT `peticao_ibfk_1` FOREIGN KEY (`tip_peticionamento`) REFERENCES `tipo_peticionamento` (`tip_peticionamento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_2` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_3` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_4` FOREIGN KEY (`cod_doc_acessorio`) REFERENCES `documento_acessorio` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_5` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT,
  ADD CONSTRAINT `peticao_ibfk_7` FOREIGN KEY (`cod_documento_vinculado`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `proposicao`
  ADD CONSTRAINT `proposicao_ibfk_1` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE SET NULL,
  ADD CONSTRAINT `proposicao_ibfk_2` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_3` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE SET NULL,
  ADD CONSTRAINT `proposicao_ibfk_4` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE SET NULL,
  ADD CONSTRAINT `proposicao_ibfk_5` FOREIGN KEY (`tip_proposicao`) REFERENCES `tipo_proposicao` (`tip_proposicao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_6` FOREIGN KEY (`cod_assunto`) REFERENCES `assunto_proposicao` (`cod_assunto`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_7` FOREIGN KEY (`cod_assessor`) REFERENCES `assessor_parlamentar` (`cod_assessor`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `proposicao_ibfk_8` FOREIGN KEY (`cod_revisor`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `proposicao_geocode`
  ADD CONSTRAINT `proposicao_geocode_ibfk_1` FOREIGN KEY (`cod_proposicao`) REFERENCES `proposicao` (`cod_proposicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `protocolo`
  ADD CONSTRAINT `protocolo_ibfk_1` FOREIGN KEY (`cod_autor`) REFERENCES `autor` (`cod_autor`) ON DELETE RESTRICT,
  ADD CONSTRAINT `protocolo_ibfk_2` FOREIGN KEY (`cod_materia_principal`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE SET NULL;

ALTER TABLE `registro_votacao`
  ADD CONSTRAINT `registro_votacao_ibfk_1` FOREIGN KEY (`cod_emenda`) REFERENCES `emenda` (`cod_emenda`) ON DELETE RESTRICT,
  ADD CONSTRAINT `registro_votacao_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT,
  ADD CONSTRAINT `registro_votacao_ibfk_3` FOREIGN KEY (`cod_parecer`) REFERENCES `relatoria` (`cod_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `registro_votacao_ibfk_4` FOREIGN KEY (`cod_substitutivo`) REFERENCES `substitutivo` (`cod_substitutivo`) ON DELETE RESTRICT;

ALTER TABLE `registro_votacao_parlamentar`
  ADD CONSTRAINT `registro_votacao_parlamentar_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `registro_votacao_parlamentar_ibfk_2` FOREIGN KEY (`cod_votacao`) REFERENCES `registro_votacao` (`cod_votacao`) ON DELETE CASCADE;

ALTER TABLE `relatoria`
  ADD CONSTRAINT `relatoria_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `relatoria_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `relatoria_ibfk_3` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `relatoria_ibfk_4` FOREIGN KEY (`tip_fim_relatoria`) REFERENCES `tipo_fim_relatoria` (`tip_fim_relatoria`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `reuniao_comissao`
  ADD CONSTRAINT `reuniao_comissao_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT;

ALTER TABLE `reuniao_comissao_pauta`
  ADD CONSTRAINT `reuniao_comissao_pauta_ibfk_1` FOREIGN KEY (`cod_reuniao`) REFERENCES `reuniao_comissao` (`cod_reuniao`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `reuniao_comissao_pauta_ibfk_2` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `reuniao_comissao_pauta_ibfk_3` FOREIGN KEY (`cod_relator`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `reuniao_comissao_presenca`
  ADD CONSTRAINT `reuniao_comissao_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `reuniao_comissao_presenca_ibfk_2` FOREIGN KEY (`cod_reuniao`) REFERENCES `reuniao_comissao` (`cod_reuniao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `sessao_legislativa`
  ADD CONSTRAINT `sessao_legislativa_ibfk_1` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `sessao_plenaria`
  ADD CONSTRAINT `sessao_plenaria_ibfk_1` FOREIGN KEY (`cod_sessao_leg`) REFERENCES `sessao_legislativa` (`cod_sessao_leg`) ON DELETE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_ibfk_3` FOREIGN KEY (`num_legislatura`) REFERENCES `legislatura` (`num_legislatura`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_ibfk_4` FOREIGN KEY (`cod_periodo_sessao`) REFERENCES `periodo_sessao` (`cod_periodo`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_ibfk_5` FOREIGN KEY (`tip_sessao`) REFERENCES `tipo_sessao_plenaria` (`tip_sessao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `sessao_plenaria_painel`
  ADD CONSTRAINT `sessao_plenaria_painel_ibfk_1` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `sessao_plenaria_presenca`
  ADD CONSTRAINT `sessao_plenaria_presenca_ibfk_1` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT,
  ADD CONSTRAINT `sessao_plenaria_presenca_ibfk_2` FOREIGN KEY (`cod_sessao_plen`) REFERENCES `sessao_plenaria` (`cod_sessao_plen`) ON DELETE CASCADE;

ALTER TABLE `substitutivo`
  ADD CONSTRAINT `substitutivo_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE;

ALTER TABLE `tramitacao`
  ADD CONSTRAINT `tramitacao_ibfk_1` FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa` (`cod_materia`) ON DELETE CASCADE,
  ADD CONSTRAINT `tramitacao_ibfk_2` FOREIGN KEY (`cod_status`) REFERENCES `status_tramitacao` (`cod_status`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_3` FOREIGN KEY (`cod_unid_tram_local`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_4` FOREIGN KEY (`cod_unid_tram_dest`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_5` FOREIGN KEY (`cod_usuario_local`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_ibfk_6` FOREIGN KEY (`cod_usuario_dest`) REFERENCES `usuario` (`cod_usuario`) ON DELETE SET NULL,
  ADD CONSTRAINT `tramitacao_ibfk_7` FOREIGN KEY (`cod_usuario_visualiza`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `tramitacao_administrativo`
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_1` FOREIGN KEY (`cod_documento`) REFERENCES `documento_administrativo` (`cod_documento`) ON DELETE CASCADE,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_2` FOREIGN KEY (`cod_status`) REFERENCES `status_tramitacao_administrativo` (`cod_status`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_3` FOREIGN KEY (`cod_unid_tram_dest`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_4` FOREIGN KEY (`cod_unid_tram_local`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_5` FOREIGN KEY (`cod_usuario_local`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_6` FOREIGN KEY (`cod_usuario_dest`) REFERENCES `usuario` (`cod_usuario`) ON DELETE SET NULL,
  ADD CONSTRAINT `tramitacao_administrativo_ibfk_7` FOREIGN KEY (`cod_usuario_visualiza`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `unidade_tramitacao`
  ADD CONSTRAINT `unidade_tramitacao_ibfk_1` FOREIGN KEY (`cod_comissao`) REFERENCES `comissao` (`cod_comissao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `unidade_tramitacao_ibfk_2` FOREIGN KEY (`cod_orgao`) REFERENCES `orgao` (`cod_orgao`) ON DELETE RESTRICT,
  ADD CONSTRAINT `unidade_tramitacao_ibfk_3` FOREIGN KEY (`cod_parlamentar`) REFERENCES `parlamentar` (`cod_parlamentar`) ON DELETE RESTRICT;

ALTER TABLE `usuario`
  ADD CONSTRAINT `usuario_ibfk_1` FOREIGN KEY (`cod_localidade_resid`) REFERENCES `localidade` (`cod_localidade`) ON DELETE RESTRICT;

ALTER TABLE `usuario_peticionamento`
  ADD CONSTRAINT `usuario_peticionamento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `usuario_peticionamento_ibfk_2` FOREIGN KEY (`tip_peticionamento`) REFERENCES `tipo_peticionamento` (`tip_peticionamento`) ON DELETE RESTRICT;

ALTER TABLE `usuario_tipo_documento`
  ADD CONSTRAINT `usuario_tipo_documento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT,
  ADD CONSTRAINT `usuario_tipo_documento_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `usuario_unid_tram`
  ADD CONSTRAINT `usuario_unid_tram_ibfk_1` FOREIGN KEY (`cod_unid_tramitacao`) REFERENCES `unidade_tramitacao` (`cod_unid_tramitacao`) ON DELETE CASCADE,
  ADD CONSTRAINT `usuario_unid_tram_ibfk_2` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE CASCADE;

ALTER TABLE `vinculo_norma_juridica`
  ADD CONSTRAINT `vinculo_norma_juridica_ibfk_1` FOREIGN KEY (`cod_norma_referente`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE,
  ADD CONSTRAINT `vinculo_norma_juridica_ibfk_2` FOREIGN KEY (`cod_norma_referida`) REFERENCES `norma_juridica` (`cod_norma`) ON DELETE CASCADE;

ALTER TABLE `visita`
  ADD CONSTRAINT `visita_ibfk_2` FOREIGN KEY (`cod_pessoa`) REFERENCES `pessoa` (`cod_pessoa`) ON DELETE CASCADE,
  ADD CONSTRAINT `visita_ibfk_3` FOREIGN KEY (`cod_funcionario`) REFERENCES `funcionario` (`cod_funcionario`) ON DELETE RESTRICT ON UPDATE RESTRICT;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
