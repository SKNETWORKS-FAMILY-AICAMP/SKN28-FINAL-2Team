from mysql.connector.django.base import DatabaseWrapper as ConnectorDatabaseWrapper


class DatabaseWrapper(ConnectorDatabaseWrapper):
    display_name = "MySQL"
