-- Script para verificar quais índices já existem no banco
-- Execute: mysql -u root -p openlegis < verificar_indices_existentes.sql

USE openlegis;

SELECT 
    TABLE_NAME as 'Tabela',
    INDEX_NAME as 'Índice'
FROM 
    information_schema.STATISTICS
WHERE 
    TABLE_SCHEMA = 'openlegis'
    AND INDEX_NAME LIKE 'idx_%'
ORDER BY 
    TABLE_NAME, INDEX_NAME;
