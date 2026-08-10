"""
One-time setup script: creates the Databricks secret scope (if needed) and
stores the Lakebase connection URL (a native-password Postgres role's
connection string). Run this once from a Databricks notebook in your
workspace (%sh python setup_secrets.py) or locally with the Databricks CLI
authenticated - never commit the resulting secret value anywhere.

Uses key "ticketing-lakebase-url" (not the plain "lakebase-url" key some of
this workspace's other bootcamp apps use in the same "database" scope) so
this app's secret can't collide with / overwrite theirs.

Usage:
    python setup_secrets.py
"""

import getpass
import logging

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists
from databricks.sdk.service import workspace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup-secrets")

w = WorkspaceClient()

SCOPE = "database"
KEY = "ticketing-lakebase-url"

try:
    w.secrets.create_scope(scope=SCOPE)
except ResourceAlreadyExists:
    logger.info("Secret scope %r already exists - reusing it.", SCOPE)

w.secrets.put_secret(
    scope=SCOPE,
    key=KEY,
    string_value=getpass.getpass("Paste your Lakebase connection URL: "),
)

w.secrets.put_acl(
    scope=SCOPE,
    principal="users",
    permission=workspace.AclPermission.READ,
)

logger.info("Stored secret %s/%s", SCOPE, KEY)
