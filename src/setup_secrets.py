"""
One-time setup script: creates the Databricks secret scope and stores the
Lakebase connection URL (a native-password Postgres role's connection
string). Run this once from a Databricks notebook in your workspace
(%sh python setup_secrets.py) or locally with the Databricks CLI
authenticated - never commit the resulting secret value anywhere.

Usage:
    python setup_secrets.py
"""

import getpass

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace

w = WorkspaceClient()

w.secrets.create_scope(scope="database")
w.secrets.put_secret(
    scope="database",
    key="lakebase-url",
    string_value=getpass.getpass("Paste your Lakebase connection URL: "),
)

w.secrets.put_acl(
    scope="database",
    principal="users",
    permission=workspace.AclPermission.READ,
)

print("Stored secret database/lakebase-url")
