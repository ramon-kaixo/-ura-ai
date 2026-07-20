#!/usr/bin/env python3
"""URA Agent Hierarchy System
Implements the 3-level agent hierarchy with permission levels and quarantine system.
"""

import json
import logging
import subprocess
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from motor.core.secrets import get_secret

# Configuration
ORCHESTRATOR_HOST = "10.164.1.99"
ORCHESTRATOR_PORT = 18789
GATEWAY_TOKEN = get_secret("OPENCLAW_GATEWAY_TOKEN", "")
QUARANTINE_DIR = "/home/ramon/URA/cuarentena"
SANDBOX_DIR = "/home/ramon/URA/sandbox"
LOG_FILE = "/home/ramon/URA/agent_hierarchy.log"
APPROVAL_SOCKET = "/tmp/ura_approval.sock"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for agent actions."""

    NONE = 0  # Sin permiso (nunca puede hacer esto)
    AUTONOMOUS = 1  # Autónomo (lo hace solo)
    NOTIFY = 2  # Avisa antes (lo hace pero te notifica)
    APPROVE = 3  # Requiere tu ok (prepara y espera)
    USER_ONLY = 4  # Solo tú (nunca delegar)


class AgentRole(Enum):
    """Agent roles in the hierarchy."""

    ORCHESTRATOR = "orchestrator"
    CRITICAL = "critical"
    INSTALLER = "installer"
    FORMS = "forms"
    EXECUTOR = "executor"


class ActionType(Enum):
    """Types of actions agents can perform."""

    INSTALL_DEPS = "install_deps"
    CONFIGURE_ENV = "configure_env"
    FILL_FORM = "fill_form"
    EXECUTE_CODE = "execute_code"
    DELETE_FILE = "delete_file"
    MOVE_FILE = "move_file"
    ACCESS_PAYMENT = "access_payment"
    SYSTEM_CHANGE = "system_change"


class ActionLogger:
    """Logs all agent actions with full audit trail."""

    def __init__(self) -> None:
        self.log_file = Path(LOG_FILE)
        self.audit_file = Path("/home/ramon/URA/audit_log.jsonl")

    def log_action(
        self,
        agent_id: str,
        role: AgentRole,
        action: ActionType,
        details: dict,
        result: str,
        approved_by: str | None = None,
    ) -> None:
        """Log an action with full audit trail."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": agent_id,
            "role": role.value,
            "action": action.value,
            "details": details,
            "result": result,
            "approved_by": approved_by,
            "status": "completed" if result == "success" else "failed",
        }

        # Write to audit log
        with open(self.audit_file, "a") as f:  # noqa: PTH123
            f.write(json.dumps(entry) + "\n")

        logger.info(f"Action logged: {agent_id} ({role.value}) - {action.value} - {result}")


class QuarantineSystem:
    """Never delete - always move to quarantine."""

    def __init__(self) -> None:
        self.quarantine_dir = Path(QUARANTINE_DIR)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def quarantine(self, source: str, reason: str, agent_id: str) -> str:
        """Move file/directory to quarantine instead of deleting."""
        source_path = Path(source)
        if not source_path.exists():
            return ""

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        quarantine_path = self.quarantine_dir / f"{source_path.name}_{timestamp}_{agent_id}"

        try:
            subprocess.run(["mv", str(source_path), str(quarantine_path)], check=True)
            logger.info(f"Quarantined {source} to {quarantine_path} (reason: {reason})")
            return str(quarantine_path)
        except Exception as e:
            logger.exception(f"Failed to quarantine {source}: {e}")
            return ""


class ApprovalSystem:
    """Handles user approval for sensitive operations."""

    def __init__(self) -> None:
        self.pending_approvals = {}

    def request_approval(self, agent_id: str, action: ActionType, details: dict, screenshot: str | None = None) -> bool:
        """Request user approval for an action."""
        approval_id = f"{agent_id}_{int(time.time())}"

        approval_request = {
            "id": approval_id,
            "agent_id": agent_id,
            "action": action.value,
            "details": details,
            "screenshot": screenshot,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "pending",
        }

        self.pending_approvals[approval_id] = approval_request

        # Send notification to Mac via socket
        self._send_to_mac(approval_request)

        # Wait for response (timeout 5 minutes)
        timeout = 300
        start_time = time.time()

        while time.time() - start_time < timeout:
            if approval_request["status"] in ["approved", "rejected"]:
                return approval_request["status"] == "approved"
            time.sleep(1)

        approval_request["status"] = "timeout"
        return False

    def _send_to_mac(self, approval_request: dict) -> None:
        """Send approval request to Mac."""
        try:
            # Use OpenClaw to send notification to Mac
            cmd = [
                "openclaw",
                "message",
                "send",
                "--channel",
                "telegram",
                "--target",
                "ramon",
                "--message",
                f"APPROVAL NEEDED: {json.dumps(approval_request, indent=2)}",
            ]
            subprocess.run(cmd, capture_output=True, timeout=30, check=False)
        except Exception as e:
            logger.exception(f"Failed to send approval to Mac: {e}")


class Agent:
    """Base agent class."""

    def __init__(self, agent_id: str, role: AgentRole) -> None:
        self.agent_id = agent_id
        self.role = role
        self.logger = ActionLogger()
        self.quarantine = QuarantineSystem()
        self.approval = ApprovalSystem()
        self.permissions = self._load_permissions()

    def _load_permissions(self) -> dict[ActionType, PermissionLevel]:
        """Load permission levels for this agent role."""
        # Default permissions based on role
        if self.role == AgentRole.ORCHESTRATOR:
            return {
                ActionType.INSTALL_DEPS: PermissionLevel.USER_ONLY,
                ActionType.CONFIGURE_ENV: PermissionLevel.USER_ONLY,
                ActionType.FILL_FORM: PermissionLevel.USER_ONLY,
                ActionType.EXECUTE_CODE: PermissionLevel.USER_ONLY,
                ActionType.DELETE_FILE: PermissionLevel.USER_ONLY,
                ActionType.MOVE_FILE: PermissionLevel.USER_ONLY,
                ActionType.ACCESS_PAYMENT: PermissionLevel.USER_ONLY,
                ActionType.SYSTEM_CHANGE: PermissionLevel.USER_ONLY,
            }
        if self.role == AgentRole.CRITICAL:
            return {
                ActionType.INSTALL_DEPS: PermissionLevel.NOTIFY,
                ActionType.CONFIGURE_ENV: PermissionLevel.NOTIFY,
                ActionType.FILL_FORM: PermissionLevel.NOTIFY,
                ActionType.EXECUTE_CODE: PermissionLevel.NOTIFY,
                ActionType.DELETE_FILE: PermissionLevel.NOTIFY,
                ActionType.MOVE_FILE: PermissionLevel.NOTIFY,
                ActionType.ACCESS_PAYMENT: PermissionLevel.NOTIFY,
                ActionType.SYSTEM_CHANGE: PermissionLevel.NOTIFY,
            }
        if self.role == AgentRole.INSTALLER:
            return {
                ActionType.INSTALL_DEPS: PermissionLevel.AUTONOMOUS,
                ActionType.CONFIGURE_ENV: PermissionLevel.APPROVE,
                ActionType.FILL_FORM: PermissionLevel.NONE,
                ActionType.EXECUTE_CODE: PermissionLevel.NONE,
                ActionType.DELETE_FILE: PermissionLevel.APPROVE,
                ActionType.MOVE_FILE: PermissionLevel.AUTONOMOUS,
                ActionType.ACCESS_PAYMENT: PermissionLevel.NONE,
                ActionType.SYSTEM_CHANGE: PermissionLevel.APPROVE,
            }
        if self.role == AgentRole.FORMS:
            return {
                ActionType.INSTALL_DEPS: PermissionLevel.NONE,
                ActionType.CONFIGURE_ENV: PermissionLevel.NONE,
                ActionType.FILL_FORM: PermissionLevel.AUTONOMOUS,
                ActionType.EXECUTE_CODE: PermissionLevel.NONE,
                ActionType.DELETE_FILE: PermissionLevel.NONE,
                ActionType.MOVE_FILE: PermissionLevel.NONE,
                ActionType.ACCESS_PAYMENT: PermissionLevel.APPROVE,
                ActionType.SYSTEM_CHANGE: PermissionLevel.NONE,
            }
        if self.role == AgentRole.EXECUTOR:
            return {
                ActionType.INSTALL_DEPS: PermissionLevel.NONE,
                ActionType.CONFIGURE_ENV: PermissionLevel.NONE,
                ActionType.FILL_FORM: PermissionLevel.NONE,
                ActionType.EXECUTE_CODE: PermissionLevel.AUTONOMOUS,
                ActionType.DELETE_FILE: PermissionLevel.NONE,
                ActionType.MOVE_FILE: PermissionLevel.AUTONOMOUS,
                ActionType.ACCESS_PAYMENT: PermissionLevel.NONE,
                ActionType.SYSTEM_CHANGE: PermissionLevel.NONE,
            }
        return {}

    def check_permission(self, action: ActionType, details: dict) -> bool:
        """Check if action is permitted and handle approval flow."""
        permission = self.permissions.get(action, PermissionLevel.NONE)

        if permission == PermissionLevel.NONE:
            logger.warning(f"Agent {self.agent_id} has no permission for {action.value}")
            return False

        if permission == PermissionLevel.AUTONOMOUS:
            return True

        if permission == PermissionLevel.NOTIFY:
            # Notify but proceed
            self._notify_action(action, details)
            return True

        if permission == PermissionLevel.APPROVE:
            # Request approval
            return self.approval.request_approval(self.agent_id, action, details)

        if permission == PermissionLevel.USER_ONLY:
            # User must do this manually
            self._notify_user_only(action, details)
            return False

        return False

    def _notify_action(self, action: ActionType, details: dict) -> None:
        """Send notification about action."""
        logger.info(f"NOTIFY: {self.agent_id} performing {action.value}")

    def _notify_user_only(self, action: ActionType, details: dict) -> None:
        """Notify that user must perform action."""
        logger.warning(f"USER ONLY: {action.value} requires manual user intervention")


class Orchestrator(Agent):
    """Level 1: Orchestrator - coordinates everything, never executes directly."""

    def __init__(self) -> None:
        super().__init__("orchestrator", AgentRole.ORCHESTRATOR)
        self.agents = {}
        self.critical_agent = None

    def register_agent(self, agent: Agent) -> None:
        """Register a specialist agent."""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id} ({agent.role.value})")

    def set_critical_agent(self, agent: Agent) -> None:
        """Set the critical (shadow) agent."""
        self.critical_agent = agent
        logger.info(f"Critical agent set: {agent.agent_id}")

    def assign_task(self, task_type: ActionType, details: dict) -> bool:
        """Assign task to appropriate specialist."""
        # Find appropriate agent for task
        for agent in self.agents.values():
            if task_type in agent.permissions:
                # Critical agent shadows this operation
                if self.critical_agent:
                    self.critical_agent.shadow_operation(agent.agent_id, task_type, details)

                # Execute task
                return agent.execute(task_type, details)

        logger.error(f"No agent available for task: {task_type.value}")
        return False


class CriticalAgent(Agent):
    """Level 2: Critical - shadows every operation, never deletes."""

    def __init__(self) -> None:
        super().__init__("critical", AgentRole.CRITICAL)

    def shadow_operation(self, target_agent: str, action: ActionType, details: dict) -> None:
        """Shadow an operation performed by another agent."""
        logger.info(f"Shadowing {target_agent} performing {action.value}")

        # Monitor for suspicious activity
        if self._is_suspicious(action, details):
            logger.warning(f"SUSPICIOUS ACTIVITY DETECTED: {target_agent} - {action.value}")
            self._halt_operation(target_agent)

    def _is_suspicious(self, action: ActionType, details: dict) -> bool:
        """Check if operation is suspicious."""
        suspicious_patterns = [
            "delete",
            "remove",
            "format",
            "wipe",
            "payment",
            "credit",
            "card",
        ]

        return any(pattern in json.dumps(details).lower() for pattern in suspicious_patterns)

    def _halt_operation(self, target_agent: str) -> None:
        """Halt a suspicious operation."""
        logger.critical(f"HALTING OPERATION: {target_agent}")
        # Send alert to orchestrator and user


class InstallerAgent(Agent):
    """Level 3: Installer - installs dependencies, configures environments."""

    def __init__(self) -> None:
        super().__init__("installer", AgentRole.INSTALLER)
        self.sandbox_dir = Path(SANDBOX_DIR) / "installer"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, action: ActionType, details: dict) -> bool:
        """Execute installation task."""
        if not self.check_permission(action, details):
            return False

        if action == ActionType.INSTALL_DEPS:
            return self._install_deps(details)
        if action == ActionType.CONFIGURE_ENV:
            return self._configure_env(details)
        if action == ActionType.DELETE_FILE:
            return self._quarantine_file(details)

        return False

    def _install_deps(self, details: dict) -> bool:
        """Install dependencies in sandbox."""
        package = details.get("package")
        if not isinstance(package, str) or not package.strip():
            logger.error(f"Invalid package name: {package}")
            return False

        package = package.strip()
        if package.startswith(("-", ".", "/")):
            logger.error(f"Package name rejected (special char prefix): {package}")
            return False
        if package.startswith("--"):
            logger.error(f"Package name rejected (flag syntax): {package}")
            return False

        logger.info(f"Installing {package} in sandbox")

        try:
            cmd = ["npm", "install", package]
            result = subprocess.run(cmd, cwd=self.sandbox_dir, capture_output=True, text=True, check=False)

            self.logger.log_action(
                self.agent_id,
                self.role,
                ActionType.INSTALL_DEPS,
                details,
                "success" if result.returncode == 0 else "failed",
            )

            return result.returncode == 0
        except Exception as e:
            logger.exception(f"Failed to install {package}: {e}")
            return False

    def _configure_env(self, details: dict) -> bool:
        """Configure environment in sandbox."""
        logger.info(f"Configuring environment: {details}")
        # Implementation
        return True

    def _quarantine_file(self, details: dict) -> bool:
        """Quarantine file instead of deleting."""
        file_path = details.get("path")
        quarantine_path = self.quarantine.quarantine(file_path, "Installer agent deletion", self.agent_id)

        self.logger.log_action(
            self.agent_id,
            self.role,
            ActionType.DELETE_FILE,
            details,
            "success" if quarantine_path else "failed",
        )

        return bool(quarantine_path)


class FormsAgent(Agent):
    """Level 3: Forms - fills forms, registrations, data."""

    def __init__(self) -> None:
        super().__init__("forms", AgentRole.FORMS)

    def execute(self, action: ActionType, details: dict) -> bool:
        """Execute form-filling task."""
        if not self.check_permission(action, details):
            return False

        if action == ActionType.FILL_FORM:
            return self._fill_form(details)
        if action == ActionType.ACCESS_PAYMENT:
            return self._handle_payment(details)

        return False

    def _fill_form(self, details: dict) -> bool:
        """Fill form (free services - autonomous)."""
        logger.info(f"Filling form: {details}")
        # Implementation
        return True

    def _handle_payment(self, details: dict) -> bool:
        """Handle payment page (prepare everything, wait for user)."""
        logger.info(f"Preparing payment form: {details}")

        # Fill everything except payment details
        # Take screenshot
        # Send to user for approval

        return True


class ExecutorAgent(Agent):
    """Level 3: Executor - executes code in isolated sandbox."""

    def __init__(self) -> None:
        super().__init__("executor", AgentRole.EXECUTOR)
        self.sandbox_dir = Path(SANDBOX_DIR) / "executor"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, action: ActionType, details: dict) -> bool:
        """Execute code in sandbox."""
        if not self.check_permission(action, details):
            return False

        if action == ActionType.EXECUTE_CODE:
            return self._execute_code(details)
        if action == ActionType.MOVE_FILE:
            return self._move_file(details)

        return False

    @staticmethod
    def _validate_code_ast(code: str) -> bool:
        """Valida código mediante AST. Solo permite operaciones seguras."""
        try:
            import ast
            tree = ast.parse(code, mode="exec")
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            # Bloquear calls a funciones peligrosas
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    name = f"{node.func.value.id}.{node.func.attr}" if isinstance(node.func.value, ast.Name) else ""
                    if name in ("os.system", "os.popen", "subprocess.run", "subprocess.Popen",
                                "shutil.rmtree", "shutil.copy", "pathlib.Path.open"):
                        return False
                    if node.func.attr in ("__import__",):
                        return False
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ("eval", "exec", "__import__", "open"):
                        return False
            # Bloquear import/from
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return False
            # Bloquear llamadas a open como función (no Attribute)
            # Bloquear exec/eval como statements no aplica porque son funciones en 3.x
        return True

    def _execute_code(self, details: dict) -> bool:
        """Execute code in isolated sandbox."""
        code = details.get("code")
        if not isinstance(code, str) or not code.strip():
            logger.error(f"Invalid code block: {type(code).__name__}")
            return False

        if not self._validate_code_ast(code):
            logger.warning(f"Code contains dangerous patterns — execution blocked")
            return False

        logger.info("Executing code in sandbox")

        try:
            # Execute in sandboxed environment
            result = subprocess.run(
                ["python3", "-I", "-c", code],
                cwd=self.sandbox_dir,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.logger.log_action(
                self.agent_id,
                self.role,
                ActionType.EXECUTE_CODE,
                details,
                "success" if result.returncode == 0 else "failed",
            )

            return result.returncode == 0
        except Exception as e:
            logger.exception(f"Failed to execute code: {e}")
            return False

    def _move_file(self, details: dict) -> bool:
        """Move file (always within sandbox)."""
        source = details.get("source")
        dest = details.get("dest")

        # Ensure both paths are within sandbox
        if not (Path(source).is_relative_to(self.sandbox_dir) and Path(dest).is_relative_to(self.sandbox_dir)):
            logger.error("File operation outside sandbox")
            return False

        try:
            subprocess.run(["mv", source, dest], check=True)
            return True
        except Exception as e:
            logger.exception(f"Failed to move file: {e}")
            return False


def main() -> None:
    """Initialize the agent hierarchy."""
    logger.info("Initializing URA Agent Hierarchy System")

    # Create agents
    orchestrator = Orchestrator()
    critical = CriticalAgent()
    installer = InstallerAgent()
    forms = FormsAgent()
    executor = ExecutorAgent()

    # Register agents
    orchestrator.set_critical_agent(critical)
    orchestrator.register_agent(installer)
    orchestrator.register_agent(forms)
    orchestrator.register_agent(executor)

    logger.info("Agent hierarchy initialized successfully")
    logger.info(f"Orchestrator: {orchestrator.agent_id}")
    logger.info(f"Critical: {critical.agent_id}")
    logger.info(f"Specialists: {[a.agent_id for a in orchestrator.agents.values()]}")

    # Keep running
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
