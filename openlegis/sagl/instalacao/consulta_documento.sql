SET FOREIGN_KEY_CHECKS=0;
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE IF NOT EXISTS `usuario_consulta_documento` (
  `id` int NOT NULL AUTO_INCREMENT,
  `cod_usuario` int NOT NULL,
  `tip_documento` int NOT NULL,
  `ind_excluido` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_usuario` (`cod_usuario`),
  KEY `idx_tip_documento` (`tip_documento`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


ALTER TABLE `usuario_consulta_documento`
  ADD CONSTRAINT `usuario_consulta_documento_ibfk_1` FOREIGN KEY (`cod_usuario`) REFERENCES `usuario` (`cod_usuario`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT `usuario_consulta_documento_ibfk_2` FOREIGN KEY (`tip_documento`) REFERENCES `tipo_documento_administrativo` (`tip_documento`) ON DELETE RESTRICT ON UPDATE RESTRICT;
SET FOREIGN_KEY_CHECKS=1;
COMMIT;
