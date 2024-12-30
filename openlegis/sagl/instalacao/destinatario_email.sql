ALTER TABLE `destinatario_oficio` CHANGE `cod_documento` `cod_documento` INT NULL;

ALTER TABLE `destinatario_oficio` CHANGE `cod_instituicao` `cod_instituicao` INT NULL;

ALTER TABLE `destinatario_oficio` CHANGE `ind_excluido` `ind_excluido` INT NOT NULL DEFAULT '0';

ALTER TABLE `destinatario_oficio` ADD `cod_materia` INT NULL AFTER `cod_destinatario`;

ALTER TABLE `destinatario_oficio` ADD `cod_proposicao` INT NULL AFTER `cod_materia`;

ALTER TABLE `destinatario_oficio` ADD `nom_destinatario` VARCHAR(300) NULL AFTER `cod_instituicao`;

ALTER TABLE `destinatario_oficio` ADD `end_email` VARCHAR(100) NULL AFTER `nom_destinatario`;

ALTER TABLE `destinatario_oficio` ADD `dat_envio` DATETIME NULL AFTER `end_email`;

ALTER TABLE `destinatario_oficio` ADD `cod_usuario` INT NULL AFTER `dat_envio`;

ALTER TABLE `destinatario_oficio` ADD INDEX `idx_cod_materia` (`cod_materia`);

ALTER TABLE `destinatario_oficio` ADD INDEX `idx_cod_proposicao` (`cod_proposicao`);

ALTER TABLE `destinatario_oficio` DROP INDEX `cod_documento`, ADD INDEX `idx_cod_documento` (`cod_documento`) USING BTREE;

ALTER TABLE `destinatario_oficio` DROP INDEX `cod_instituicao`, ADD INDEX `idx_cod_instituicao` (`cod_instituicao`) USING BTREE;

ALTER TABLE `destinatario_oficio` ADD FOREIGN KEY (`cod_materia`) REFERENCES `materia_legislativa`(`cod_materia`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `destinatario_oficio` ADD FOREIGN KEY (`cod_proposicao`) REFERENCES `proposicao`(`cod_proposicao`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `destinatario_oficio` ADD FOREIGN KEY (`cod_usuario`) REFERENCES `usuario`(`cod_usuario`) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE `instituicao` CHANGE `cod_categoria` `cod_categoria` INT NULL;

ALTER TABLE `instituicao` ADD `txt_atividade` VARCHAR(10) NULL AFTER `txt_ip_alteracao`; 

ALTER TABLE `instituicao` ADD `txt_origem` VARCHAR(5) NULL AFTER `txt_atividade`; 
