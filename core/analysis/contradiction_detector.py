# core/analysis/contradiction_detector.py
"""
Module de détection de contradictions dans les documents juridiques.
"""
import re
import json
import difflib
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import streamlit as st

from core.vector_juridique import VectorJuridique
from core.llm.multi_llm_manager import MultiLLMManager


@dataclass
class Contradiction:
    """Représente une contradiction détectée."""
    type: str  # date, montant, personne, fait, lieu
    severity: str  # low, medium, high
    doc1_ref: Dict[str, Any]
    doc2_ref: Dict[str, Any]
    description: str
    confidence: float = 0.0
    impact: Optional[str] = None


class ContradictionDetector:
    """Détecte les contradictions entre documents juridiques."""
    
    def __init__(self):
        self.vector_db = VectorJuridique()
        self.llm_manager = MultiLLMManager()
        
        # Patterns de détection
        self.patterns = {
            'date': [
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
                r'\b(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})\b',
                r'\b((?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+\w+\s+\d{4})\b'
            ],
            'montant': [
                r'(\d+(?:\s?\d{3})*(?:,\d{2})?\s*(?:€|euros?|EUR))',
                r'(\d+(?:\.\d{3})*(?:,\d{2})?\s*(?:€|euros?|EUR))',
                r'((?:un|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s+(?:mille|millions?)\s+(?:d\')?euros?)'
            ],
            'personne': [
                r'\b([A-Z][a-zéèêëàâäôöûü]+(?:\s+[A-Z][a-zéèêëàâäôöûü]+)+)\b',
                r'\b(?:M\.|Mme|Mlle|Me|Dr)\s+([A-Z][a-zéèêëàâäôöûü]+(?:\s+[A-Z][a-zéèêëàâäôöûü]+)*)\b'
            ],
            'societe': [
                r'\b([A-Z][A-Z0-9\s&-]+(?:SA|SARL|SAS|EURL|SCI|SNC))\b',
                r'\bsociété\s+([A-Z][A-Za-z0-9\s&-]+)\b'
            ]
        }
        
        # Seuils de sensibilité
        self.sensitivity_thresholds = {
            'Faible': 0.8,
            'Normale': 0.6,
            'Élevée': 0.4
        }
    
    async def analyze_documents(
        self,
        documents: List[str],
        focus_types: List[str] = None,
        sensitivity: str = 'Normale',
        use_ai: bool = True
    ) -> List[Contradiction]:
        """
        Analyse plusieurs documents pour détecter des contradictions.
        
        Args:
            documents: Liste des chemins/IDs des documents
            focus_types: Types de contradictions à rechercher
            sensitivity: Niveau de sensibilité (Faible/Normale/Élevée)
            use_ai: Utiliser l'IA pour une analyse approfondie
        
        Returns:
            Liste des contradictions détectées
        """
        contradictions = []
        
        # Types à analyser
        if not focus_types:
            focus_types = ['date', 'montant', 'personne', 'fait']
        
        # Charger et analyser chaque paire de documents
        for i, doc1 in enumerate(documents):
            for doc2 in documents[i+1:]:
                # Extraire le contenu
                content1 = await self._extract_content(doc1)
                content2 = await self._extract_content(doc2)
                
                # Détection par patterns
                if 'date' in focus_types:
                    contradictions.extend(
                        self._detect_date_contradictions(content1, content2, doc1, doc2)
                    )
                
                if 'montant' in focus_types:
                    contradictions.extend(
                        self._detect_amount_contradictions(content1, content2, doc1, doc2)
                    )
                
                if 'personne' in focus_types:
                    contradictions.extend(
                        self._detect_person_contradictions(content1, content2, doc1, doc2)
                    )
                
                # Analyse IA si activée
                if use_ai and 'fait' in focus_types:
                    ai_contradictions = await self._detect_fact_contradictions_ai(
                        content1, content2, doc1, doc2
                    )
                    contradictions.extend(ai_contradictions)
        
        # Filtrer selon la sensibilité
        threshold = self.sensitivity_thresholds.get(sensitivity, 0.6)
        filtered = [c for c in contradictions if c.confidence >= threshold]
        
        # Trier par sévérité et confiance
        filtered.sort(key=lambda x: (
            {'high': 3, 'medium': 2, 'low': 1}[x.severity],
            x.confidence
        ), reverse=True)
        
        return filtered
    
    async def _extract_content(self, document: str) -> Dict[str, Any]:
        """Extrait le contenu d'un document."""
        # Utiliser la recherche vectorielle pour récupérer le contenu
        results = self.vector_db.search(document, k=10)
        
        content = {
            'text': ' '.join([r['content'] for r in results]),
            'metadata': results[0]['metadata'] if results else {},
            'chunks': results
        }
        
        return content
    
    def _detect_date_contradictions(
        self,
        content1: Dict[str, Any],
        content2: Dict[str, Any],
        doc1: str,
        doc2: str
    ) -> List[Contradiction]:
        """Détecte les contradictions de dates."""
        contradictions = []
        
        # Extraire toutes les dates
        dates1 = self._extract_dates(content1['text'])
        dates2 = self._extract_dates(content2['text'])
        
        # Comparer les contextes similaires
        for date1, context1 in dates1.items():
            for date2, context2 in dates2.items():
                similarity = self._context_similarity(context1, context2)
                
                if similarity > 0.7 and date1 != date2:
                    # Contradiction potentielle
                    diff_days = abs((date1 - date2).days)
                    
                    severity = 'low'
                    if diff_days > 30:
                        severity = 'high'
                    elif diff_days > 7:
                        severity = 'medium'
                    
                    contradictions.append(Contradiction(
                        type='date',
                        severity=severity,
                        doc1_ref={
                            'document': doc1,
                            'value': date1.strftime('%d/%m/%Y'),
                            'context': context1
                        },
                        doc2_ref={
                            'document': doc2,
                            'value': date2.strftime('%d/%m/%Y'),
                            'context': context2
                        },
                        description=f"Dates différentes pour un même événement ({diff_days} jours d'écart)",
                        confidence=similarity,
                        impact=self._assess_date_impact(context1, diff_days)
                    ))
        
        return contradictions
    
    def _detect_amount_contradictions(
        self,
        content1: Dict[str, Any],
        content2: Dict[str, Any],
        doc1: str,
        doc2: str
    ) -> List[Contradiction]:
        """Détecte les contradictions de montants."""
        contradictions = []
        
        # Extraire tous les montants
        amounts1 = self._extract_amounts(content1['text'])
        amounts2 = self._extract_amounts(content2['text'])
        
        # Comparer les contextes similaires
        for amount1, context1 in amounts1.items():
            for amount2, context2 in amounts2.items():
                similarity = self._context_similarity(context1, context2)
                
                if similarity > 0.7 and amount1 != amount2:
                    # Calcul de l'écart
                    diff = abs(amount1 - amount2)
                    diff_percent = (diff / max(amount1, amount2)) * 100
                    
                    severity = 'low'
                    if diff_percent > 20:
                        severity = 'high'
                    elif diff_percent > 10:
                        severity = 'medium'
                    
                    contradictions.append(Contradiction(
                        type='montant',
                        severity=severity,
                        doc1_ref={
                            'document': doc1,
                            'value': f"{amount1:,.2f} €",
                            'context': context1
                        },
                        doc2_ref={
                            'document': doc2,
                            'value': f"{amount2:,.2f} €",
                            'context': context2
                        },
                        description=f"Montants différents ({diff_percent:.1f}% d'écart)",
                        confidence=similarity,
                        impact=self._assess_amount_impact(context1, diff)
                    ))
        
        return contradictions
    
    def _detect_person_contradictions(
        self,
        content1: Dict[str, Any],
        content2: Dict[str, Any],
        doc1: str,
        doc2: str
    ) -> List[Contradiction]:
        """Détecte les contradictions sur les personnes."""
        contradictions = []
        
        # Extraire les personnes et leurs rôles
        persons1 = self._extract_persons_with_roles(content1['text'])
        persons2 = self._extract_persons_with_roles(content2['text'])
        
        # Identifier les contradictions de rôles
        for person, roles1 in persons1.items():
            if person in persons2:
                roles2 = persons2[person]
                
                # Rôles contradictoires
                conflicting = self._find_conflicting_roles(roles1, roles2)
                if conflicting:
                    contradictions.append(Contradiction(
                        type='personne',
                        severity='medium',
                        doc1_ref={
                            'document': doc1,
                            'value': person,
                            'context': f"Rôles: {', '.join(roles1)}"
                        },
                        doc2_ref={
                            'document': doc2,
                            'value': person,
                            'context': f"Rôles: {', '.join(roles2)}"
                        },
                        description=f"Rôles contradictoires pour {person}",
                        confidence=0.8,
                        impact="Peut affecter la crédibilité des témoignages"
                    ))
        
        return contradictions
    
    async def _detect_fact_contradictions_ai(
        self,
        content1: Dict[str, Any],
        content2: Dict[str, Any],
        doc1: str,
        doc2: str
    ) -> List[Contradiction]:
        """Utilise l'IA pour détecter des contradictions factuelles complexes."""
        
        prompt = f"""En tant qu'expert juridique, analysez ces deux extraits et identifiez les contradictions factuelles.

Document 1 ({doc1}):
{content1['text'][:2000]}

Document 2 ({doc2}):
{content2['text'][:2000]}

Pour chaque contradiction trouvée, indiquez:
1. La nature exacte de la contradiction
2. Les passages contradictoires dans chaque document
3. L'impact potentiel sur le dossier (faible/moyen/élevé)
4. Votre niveau de confiance (0-100%)

Format JSON attendu:
{{
    "contradictions": [
        {{
            "description": "...",
            "doc1_passage": "...",
            "doc2_passage": "...",
            "impact": "low/medium/high",
            "confidence": 85
        }}
    ]
}}"""

        # Interroger l'IA
        response = await self.llm_manager.query_multiple(
            prompt=prompt,
            context="",
            selected_models=['GPT-4o'],
            progress_callback=None
        )
        
        contradictions = []
        
        try:
            # Parser la réponse
            ai_results = json.loads(response['responses']['GPT-4o']['content'])
            
            for item in ai_results.get('contradictions', []):
                contradictions.append(Contradiction(
                    type='fait',
                    severity=item.get('impact', 'medium'),
                    doc1_ref={
                        'document': doc1,
                        'value': 'Voir contexte',
                        'context': item.get('doc1_passage', '')[:200]
                    },
                    doc2_ref={
                        'document': doc2,
                        'value': 'Voir contexte',
                        'context': item.get('doc2_passage', '')[:200]
                    },
                    description=item.get('description', 'Contradiction factuelle'),
                    confidence=item.get('confidence', 70) / 100,
                    impact=self._translate_impact(item.get('impact', 'medium'))
                ))
        except:
            # En cas d'erreur de parsing
            pass
        
        return contradictions
    
    def _extract_dates(self, text: str) -> Dict[date, str]:
        """Extrait les dates avec leur contexte."""
        dates = {}
        
        for pattern in self.patterns['date']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    # Parser la date
                    date_str = match.group(1)
                    parsed_date = self._parse_date(date_str)
                    
                    if parsed_date:
                        # Extraire le contexte (50 chars avant/après)
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 50)
                        context = text[start:end].strip()
                        
                        dates[parsed_date] = context
                except:
                    continue
        
        return dates
    
    def _extract_amounts(self, text: str) -> Dict[float, str]:
        """Extrait les montants avec leur contexte."""
        amounts = {}
        
        for pattern in self.patterns['montant']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    # Parser le montant
                    amount_str = match.group(1)
                    amount = self._parse_amount(amount_str)
                    
                    if amount:
                        # Extraire le contexte
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 50)
                        context = text[start:end].strip()
                        
                        amounts[amount] = context
                except:
                    continue
        
        return amounts
    
    def _extract_persons_with_roles(self, text: str) -> Dict[str, List[str]]:
        """Extrait les personnes avec leurs rôles."""
        persons = {}
        
        # Patterns pour les rôles
        role_patterns = [
            r'(?:le|la)\s+(?:prévenu|mis en cause|témoin|victime|plaignant|expert|avocat)',
            r'(?:en qualité de|en tant que)\s+(\w+)',
            r'(?:gérant|président|directeur|administrateur|associé|salarié|comptable)'
        ]
        
        for pattern in self.patterns['personne']:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                person = match.group(1)
                
                # Chercher les rôles dans le contexte
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]
                
                roles = []
                for role_pattern in role_patterns:
                    role_match = re.search(role_pattern, context, re.IGNORECASE)
                    if role_match:
                        roles.append(role_match.group(0))
                
                if person not in persons:
                    persons[person] = []
                persons[person].extend(roles)
        
        return persons
    
    def _context_similarity(self, context1: str, context2: str) -> float:
        """Calcule la similarité entre deux contextes."""
        # Normaliser les textes
        context1 = context1.lower().strip()
        context2 = context2.lower().strip()
        
        # Utiliser difflib pour la similarité
        return difflib.SequenceMatcher(None, context1, context2).ratio()
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse une date depuis différents formats."""
        # Formats à essayer
        formats = [
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d %B %Y',
            '%d/%m/%y',
            '%d-%m-%y'
        ]
        
        # Remplacer les mois français
        mois_fr = {
            'janvier': 'January', 'février': 'February', 'mars': 'March',
            'avril': 'April', 'mai': 'May', 'juin': 'June',
            'juillet': 'July', 'août': 'August', 'septembre': 'September',
            'octobre': 'October', 'novembre': 'November', 'décembre': 'December'
        }
        
        for fr, en in mois_fr.items():
            date_str = date_str.replace(fr, en)
        
        # Essayer les formats
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except:
                continue
        
        return None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse un montant depuis différents formats."""
        # Nettoyer la chaîne
        amount_str = amount_str.replace('€', '').replace('EUR', '').strip()
        amount_str = amount_str.replace(' ', '').replace('\xa0', '')
        
        # Gérer les formats français vs anglais
        if ',' in amount_str and '.' in amount_str:
            # Format français probable (1.234,56)
            amount_str = amount_str.replace('.', '').replace(',', '.')
        elif ',' in amount_str:
            # Virgule seule - déterminer si c'est décimal ou milliers
            parts = amount_str.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                # Probablement décimal français
                amount_str = amount_str.replace(',', '.')
            else:
                # Probablement milliers anglais
                amount_str = amount_str.replace(',', '')
        
        try:
            return float(amount_str)
        except:
            return None
    
    def _find_conflicting_roles(self, roles1: List[str], roles2: List[str]) -> List[Tuple[str, str]]:
        """Trouve les rôles contradictoires."""
        conflicts = []
        
        # Paires de rôles incompatibles
        incompatible = [
            ('témoin', 'prévenu'),
            ('victime', 'mis en cause'),
            ('expert', 'partie'),
            ('avocat', 'témoin')
        ]
        
        for role1 in roles1:
            for role2 in roles2:
                for pair in incompatible:
                    if (pair[0] in role1 and pair[1] in role2) or \
                       (pair[1] in role1 and pair[0] in role2):
                        conflicts.append((role1, role2))
        
        return conflicts
    
    def _assess_date_impact(self, context: str, diff_days: int) -> str:
        """Évalue l'impact d'une contradiction de date."""
        # Mots-clés critiques
        critical_keywords = ['prescription', 'délai', 'forclusion', 'caducité', 'péremption']
        
        for keyword in critical_keywords:
            if keyword in context.lower():
                return f"CRITIQUE: Peut affecter la {keyword}"
        
        if diff_days > 365:
            return "Impact potentiel sur la prescription"
        elif diff_days > 30:
            return "Impact possible sur la chronologie des faits"
        else:
            return "Impact limité"
    
    def _assess_amount_impact(self, context: str, diff: float) -> str:
        """Évalue l'impact d'une contradiction de montant."""
        # Mots-clés importants
        keywords = {
            'préjudice': "Affecte l'évaluation du préjudice",
            'détournement': "Modifie la qualification pénale",
            'fraude': "Impact sur la caractérisation de la fraude",
            'taxe': "Conséquences fiscales",
            'amende': "Modifie les sanctions encourues"
        }
        
        for keyword, impact in keywords.items():
            if keyword in context.lower():
                return impact
        
        if diff > 100000:
            return "Impact majeur sur l'évaluation financière"
        elif diff > 10000:
            return "Impact significatif"
        else:
            return "Impact modéré"
    
    def _translate_impact(self, impact: str) -> str:
        """Traduit l'impact en français."""
        translations = {
            'low': 'Impact limité',
            'medium': 'Impact modéré',
            'high': 'Impact élevé'
        }
        return translations.get(impact, impact)
    
    def generate_contradiction_report(
        self,
        contradictions: List[Contradiction],
        format: str = 'markdown'
    ) -> str:
        """Génère un rapport des contradictions détectées."""
        if format == 'markdown':
            report = ["# Rapport d'analyse des contradictions\n"]
            report.append(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            report.append(f"Nombre de contradictions détectées: {len(contradictions)}\n")
            
            # Résumé par type
            by_type = {}
            for c in contradictions:
                by_type[c.type] = by_type.get(c.type, 0) + 1
            
            report.append("## Résumé par type\n")
            for type_name, count in by_type.items():
                report.append(f"- **{type_name.capitalize()}**: {count} contradictions\n")
            
            # Détail des contradictions
            report.append("\n## Contradictions détectées\n")
            
            for i, contradiction in enumerate(contradictions, 1):
                report.append(f"### Contradiction {i} - {contradiction.type.capitalize()}\n")
                report.append(f"**Sévérité**: {contradiction.severity}\n")
                report.append(f"**Confiance**: {contradiction.confidence:.0%}\n")
                report.append(f"**Description**: {contradiction.description}\n\n")
                
                report.append("**Document 1**:\n")
                report.append(f"- Fichier: {contradiction.doc1_ref['document']}\n")
                report.append(f"- Valeur: {contradiction.doc1_ref['value']}\n")
                report.append(f"- Contexte: *{contradiction.doc1_ref['context']}*\n\n")
                
                report.append("**Document 2**:\n")
                report.append(f"- Fichier: {contradiction.doc2_ref['document']}\n")
                report.append(f"- Valeur: {contradiction.doc2_ref['value']}\n")
                report.append(f"- Contexte: *{contradiction.doc2_ref['context']}*\n\n")
                
                if contradiction.impact:
                    report.append(f"**Impact**: {contradiction.impact}\n\n")
                
                report.append("---\n\n")
            
            return ''.join(report)
        
        elif format == 'json':
            return json.dumps({
                'date': datetime.now().isoformat(),
                'total': len(contradictions),
                'contradictions': [
                    {
                        'type': c.type,
                        'severity': c.severity,
                        'confidence': c.confidence,
                        'description': c.description,
                        'doc1': c.doc1_ref,
                        'doc2': c.doc2_ref,
                        'impact': c.impact
                    }
                    for c in contradictions
                ]
            }, ensure_ascii=False, indent=2)
        
        else:
            raise ValueError(f"Format non supporté: {format}")


# Export
__all__ = ['ContradictionDetector', 'Contradiction']
