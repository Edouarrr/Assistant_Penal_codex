# core/security/rgpd_manager.py
"""Gestionnaire RGPD pour la conformité et l'audit."""
import logging
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import streamlit as st


class RGPDManager:
    """Gestionnaire pour la conformité RGPD et l'audit des accès."""
    
    def __init__(self, audit_dir: str = "logs"):
        """Initialise le gestionnaire RGPD."""
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(exist_ok=True)
        self.audit_log = self.audit_dir / "rgpd_audit.log"
        self.consent_file = self.audit_dir / "consents.json"
        self.retention_log = self.audit_dir / "retention.json"
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure le système de logging."""
        self.logger = logging.getLogger('rgpd_audit')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.FileHandler(self.audit_log, encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_access(self, user: str, action: str, document: Optional[str] = None, 
                   details: Optional[Dict[str, Any]] = None):
        """
        Enregistre un accès dans le journal d'audit.
        
        Args:
            user: Identifiant de l'utilisateur
            action: Action effectuée
            document: Document concerné (optionnel)
            details: Détails supplémentaires (optionnel)
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'user': user,
            'action': action,
            'document': document,
            'details': details or {},
            'ip': self._get_user_ip(),
            'session_id': st.session_state.get('session_id', 'unknown')
        }
        
        # Log textuel
        log_message = f"USER: {user} | ACTION: {action}"
        if document:
            log_message += f" | DOC: {document}"
        if details:
            # Limiter les détails pour éviter les logs trop longs
            details_str = str(details)[:200]
            log_message += f" | DETAILS: {details_str}"
        
        self.logger.info(log_message)
        
        # Sauvegarder aussi en JSON
        self._save_json_entry(entry)
        
        # Vérifier les alertes
        self._check_alerts(user, action)
    
    def _get_user_ip(self) -> str:
        """Récupère l'IP de l'utilisateur si possible."""
        # Dans Streamlit Cloud, c'est plus complexe
        # Pour l'instant, retourner 'unknown'
        return "unknown"
    
    def _save_json_entry(self, entry: Dict[str, Any]):
        """Sauvegarde l'entrée au format JSON."""
        json_log = self.audit_dir / "rgpd_audit.json"
        
        entries = []
        if json_log.exists():
            try:
                with open(json_log, 'r', encoding='utf-8') as f:
                    entries = json.load(f)
            except:
                entries = []
        
        entries.append(entry)
        
        # Rotation : garder seulement les 10000 dernières entrées
        if len(entries) > 10000:
            entries = entries[-10000:]
        
        with open(json_log, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    
    def _check_alerts(self, user: str, action: str):
        """Vérifie si des alertes doivent être déclenchées."""
        # Alertes pour actions sensibles
        sensitive_actions = [
            'export_data', 'delete_document', 'modify_permissions',
            'access_sensitive_doc', 'bulk_download'
        ]
        
        if action in sensitive_actions:
            self.logger.warning(f"ALERTE: Action sensible par {user}: {action}")
            # TODO: Envoyer une notification (email, Slack, etc.)
    
    def anonymize_data(self, data: Dict[str, Any], fields_to_anonymize: List[str] = None) -> Dict[str, Any]:
        """
        Anonymise les données sensibles avant export.
        
        Args:
            data: Données à anonymiser
            fields_to_anonymize: Champs à anonymiser
        
        Returns:
            Données anonymisées
        """
        if fields_to_anonymize is None:
            fields_to_anonymize = [
                'nom', 'prenom', 'email', 'telephone', 'adresse',
                'numero_ss', 'iban', 'carte_credit'
            ]
        
        anonymized = data.copy()
        
        for field in fields_to_anonymize:
            if field in anonymized:
                value = str(anonymized[field])
                
                if field in ['nom', 'prenom']:
                    # Garder première lettre + ***
                    anonymized[field] = value[0].upper() + '***' if value else '***'
                
                elif field == 'email':
                    # user***@domain.com
                    if '@' in value:
                        parts = value.split('@')
                        anonymized[field] = parts[0][:3] + '***@' + parts[1]
                    else:
                        anonymized[field] = '***'
                
                elif field == 'telephone':
                    # +33 6** ** ** **
                    if len(value) > 6:
                        anonymized[field] = value[:6] + ' ** ** ** **'
                    else:
                        anonymized[field] = '***'
                
                else:
                    # Hash pour les autres données sensibles
                    hash_value = hashlib.sha256(value.encode()).hexdigest()
                    anonymized[field] = hash_value[:8] + '***'
        
        # Ajouter un marqueur d'anonymisation
        anonymized['_anonymized'] = True
        anonymized['_anonymized_date'] = datetime.now().isoformat()
        
        return anonymized
    
    def check_consent(self, user: str, purpose: str = 'traitement_donnees') -> bool:
        """
        Vérifie si l'utilisateur a donné son consentement.
        
        Args:
            user: Identifiant utilisateur
            purpose: Finalité du traitement
        
        Returns:
            True si consentement valide
        """
        if not self.consent_file.exists():
            return False
        
        try:
            with open(self.consent_file, 'r', encoding='utf-8') as f:
                consents = json.load(f)
            
            user_consents = consents.get(user, {})
            consent = user_consents.get(purpose, {})
            
            if consent.get('status') != 'granted':
                return False
            
            # Vérifier la validité (1 an)
            consent_date = datetime.fromisoformat(consent['date'])
            if (datetime.now() - consent_date).days > 365:
                return False
            
            return True
            
        except Exception:
            return False
    
    def record_consent(self, user: str, granted: bool, purpose: str = 'traitement_donnees', 
                      details: Dict[str, Any] = None):
        """Enregistre le consentement d'un utilisateur."""
        consents = {}
        
        if self.consent_file.exists():
            try:
                with open(self.consent_file, 'r', encoding='utf-8') as f:
                    consents = json.load(f)
            except:
                consents = {}
        
        if user not in consents:
            consents[user] = {}
        
        consents[user][purpose] = {
            'status': 'granted' if granted else 'refused',
            'date': datetime.now().isoformat(),
            'details': details or {},
            'ip': self._get_user_ip()
        }
        
        with open(self.consent_file, 'w', encoding='utf-8') as f:
            json.dump(consents, f, ensure_ascii=False, indent=2)
        
        # Logger l'action
        self.log_access(
            user,
            'consent_update',
            details={'purpose': purpose, 'granted': granted}
        )
    
    def get_user_data(self, user: str) -> Dict[str, Any]:
        """
        Récupère toutes les données d'un utilisateur (droit d'accès RGPD).
        
        Args:
            user: Identifiant utilisateur
        
        Returns:
            Toutes les données concernant l'utilisateur
        """
        user_data = {
            'user_id': user,
            'export_date': datetime.now().isoformat(),
            'access_logs': [],
            'consents': {},
            'documents_accessed': set(),
            'queries': []
        }
        
        # Récupérer les logs d'accès
        if (self.audit_dir / "rgpd_audit.json").exists():
            with open(self.audit_dir / "rgpd_audit.json", 'r') as f:
                all_logs = json.load(f)
                user_logs = [log for log in all_logs if log.get('user') == user]
                user_data['access_logs'] = user_logs[-1000:]  # Derniers 1000 logs
                
                # Extraire les documents accédés
                for log in user_logs:
                    if log.get('document'):
                        user_data['documents_accessed'].add(log['document'])
        
        # Récupérer les consentements
        if self.consent_file.exists():
            with open(self.consent_file, 'r') as f:
                all_consents = json.load(f)
                user_data['consents'] = all_consents.get(user, {})
        
        # Convertir set en list pour JSON
        user_data['documents_accessed'] = list(user_data['documents_accessed'])
        
        return user_data
    
    def delete_user_data(self, user: str, confirm: bool = False) -> bool:
        """
        Supprime toutes les données d'un utilisateur (droit à l'effacement).
        
        Args:
            user: Identifiant utilisateur
            confirm: Confirmation de suppression
        
        Returns:
            True si suppression effectuée
        """
        if not confirm:
            return False
        
        # Logger l'action avant suppression
        self.log_access('system', 'user_data_deletion_requested', details={'user': user})
        
        # Anonymiser plutôt que supprimer pour garder la cohérence des logs
        
        # Anonymiser dans les logs JSON
        if (self.audit_dir / "rgpd_audit.json").exists():
            with open(self.audit_dir / "rgpd_audit.json", 'r') as f:
                logs = json.load(f)
            
            for log in logs:
                if log.get('user') == user:
                    log['user'] = f"DELETED_USER_{hashlib.sha256(user.encode()).hexdigest()[:8]}"
                    if 'details' in log:
                        log['details'] = self.anonymize_data(log['details'])
            
            with open(self.audit_dir / "rgpd_audit.json", 'w') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        
        # Supprimer les consentements
        if self.consent_file.exists():
            with open(self.consent_file, 'r') as f:
                consents = json.load(f)
            
            if user in consents:
                del consents[user]
            
            with open(self.consent_file, 'w') as f:
                json.dump(consents, f, ensure_ascii=False, indent=2)
        
        return True
    
    def generate_rgpd_report(self) -> Dict[str, Any]:
        """Génère un rapport de conformité RGPD."""
        report = {
            'generated_date': datetime.now().isoformat(),
            'total_users': set(),
            'total_accesses': 0,
            'sensitive_actions': 0,
            'consent_stats': {
                'granted': 0,
                'refused': 0,
                'expired': 0
            },
            'retention_compliance': True,
            'alerts': []
        }
        
        # Analyser les logs
        if (self.audit_dir / "rgpd_audit.json").exists():
            with open(self.audit_dir / "rgpd_audit.json", 'r') as f:
                logs = json.load(f)
                
                report['total_accesses'] = len(logs)
                
                for log in logs:
                    report['total_users'].add(log.get('user', 'unknown'))
                    
                    # Compter les actions sensibles
                    if log.get('action') in ['export_data', 'delete_document']:
                        report['sensitive_actions'] += 1
        
        # Analyser les consentements
        if self.consent_file.exists():
            with open(self.consent_file, 'r') as f:
                consents = json.load(f)
                
                for user_consents in consents.values():
                    for consent in user_consents.values():
                        if consent['status'] == 'granted':
                            # Vérifier si expiré
                            consent_date = datetime.fromisoformat(consent['date'])
                            if (datetime.now() - consent_date).days > 365:
                                report['consent_stats']['expired'] += 1
                            else:
                                report['consent_stats']['granted'] += 1
                        else:
                            report['consent_stats']['refused'] += 1
        
        # Convertir set en list
        report['total_users'] = len(report['total_users'])
        
        return report
    
    def apply_retention_policy(self, dry_run: bool = True) -> Dict[str, int]:
        """
        Applique la politique de rétention des données.
        
        Args:
            dry_run: Si True, simule seulement
        
        Returns:
            Nombre d'éléments supprimés par catégorie
        """
        retention_policy = {
            'access_logs': 365,  # 1 an
            'error_logs': 90,    # 3 mois
            'temp_files': 7,     # 7 jours
            'exports': 30        # 30 jours
        }
        
        deleted = {
            'logs': 0,
            'files': 0
        }
        
        # Nettoyer les vieux logs
        if (self.audit_dir / "rgpd_audit.json").exists():
            with open(self.audit_dir / "rgpd_audit.json", 'r') as f:
                logs = json.load(f)
            
            cutoff_date = datetime.now() - timedelta(days=retention_policy['access_logs'])
            new_logs = []
            
            for log in logs:
                log_date = datetime.fromisoformat(log['timestamp'])
                if log_date > cutoff_date:
                    new_logs.append(log)
                else:
                    deleted['logs'] += 1
            
            if not dry_run:
                with open(self.audit_dir / "rgpd_audit.json", 'w') as f:
                    json.dump(new_logs, f, ensure_ascii=False, indent=2)
        
        # Logger l'action
        if not dry_run:
            self.log_access(
                'system',
                'retention_policy_applied',
                details={'deleted': deleted}
            )
        
        return deleted


# Export
__all__ = ['RGPDManager']
