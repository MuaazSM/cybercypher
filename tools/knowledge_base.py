from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A document in the knowledge base."""
    page_content: str
    metadata: Dict[str, Any]


class KnowledgeBase:
    """
    RAG knowledge base for semantic search.
    
    In production, this would use FAISS or Pinecone.
    For MVP, implements in-memory search with fallback to empty results.
    """
    
    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize knowledge base.
        
        Args:
            persist_directory: Path for persistence (FAISS, etc)
        """
        self.persist_directory = persist_directory
        self.documents: List[Document] = []
        
        logger.info(f"[KnowledgeBase] Initialized with persist_directory: {persist_directory}")
    
    def add_document(self, content: str, metadata: Dict[str, Any]):
        """
        Add a document to the knowledge base.
        
        Args:
            content: Document text
            metadata: Metadata (type, doc_title, status, etc)
        """
        doc = Document(page_content=content, metadata=metadata)
        self.documents.append(doc)
        logger.debug(f"[KnowledgeBase] Added document: {metadata.get('doc_title', 'untitled')}")
    
    def add_incident_resolution(self, incident_id: str, title: str, resolution: str, root_cause: str):
        """
        Add a resolved incident to knowledge base.
        
        Args:
            incident_id: Incident ID
            title: Incident title
            resolution: How it was resolved
            root_cause: What caused it
        """
        content = f"""
Resolved Incident: {title}

Root Cause:
{root_cause}

Resolution:
{resolution}
"""
        self.add_document(
            content=content,
            metadata={
                "type": "incident",
                "incident_id": incident_id,
                "status": "resolved",
                "title": title
            }
        )
    
    def add_migration_guide(self, stage: int, content: str, doc_title: str):
        """
        Add migration documentation.
        
        Args:
            stage: Migration stage number
            content: Documentation content
            doc_title: Document title
        """
        self.add_document(
            content=content,
            metadata={
                "type": "migration_guide",
                "stage": stage,
                "doc_title": doc_title
            }
        )
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_by: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Semantic search over knowledge base.
        
        Args:
            query: Search query
            k: Number of results to return
            filter_by: Optional metadata filters
        
        Returns:
            List of most relevant documents
        """
        logger.debug(f"[KnowledgeBase] Searching: {query[:50]}... (k={k})")
        
        # Apply filters
        candidates = self.documents
        if filter_by:
            for key, value in filter_by.items():
                candidates = [
                    doc for doc in candidates
                    if doc.metadata.get(key) == value
                ]
        
        # Simple keyword matching (in production would use semantic embeddings)
        query_terms = set(query.lower().split())
        
        scored_docs = []
        for doc in candidates:
            content_lower = doc.page_content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                scored_docs.append((doc, score))
        
        # Sort by score and return top k
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        results = [doc for doc, _ in scored_docs[:k]]
        
        logger.info(f"[KnowledgeBase] Found {len(results)} documents matching query")
        return results
    
    def get_all(self, doc_type: Optional[str] = None) -> List[Document]:
        """
        Get all documents, optionally filtered by type.
        
        Args:
            doc_type: Optional document type filter
        
        Returns:
            List of documents
        """
        if doc_type:
            return [doc for doc in self.documents if doc.metadata.get("type") == doc_type]
        return self.documents
    
    def clear(self):
        """Clear all documents from knowledge base."""
        self.documents = []
        logger.info("[KnowledgeBase] Cleared all documents")
    
    @staticmethod
    def seed_knowledge_base(kb: "KnowledgeBase"):
        """
        Seed knowledge base with example data.
        
        Args:
            kb: KnowledgeBase instance to seed
        """
        # Add sample resolved incidents
        kb.add_incident_resolution(
            incident_id="incident_001",
            title="Webhook delivery failures in Stage 2",
            root_cause="Merchants didn't complete webhook endpoint configuration",
            resolution="Updated Stage 2 guide with clearer webhook setup steps. Added email reminder to merchants."
        )
        
        kb.add_incident_resolution(
            incident_id="incident_002",
            title="API authentication failures across Stage 3",
            root_cause="API token generation changed, merchants using old token format",
            resolution="Pushed deprecation notice 30 days before change. Added backward compatibility layer."
        )
        
        kb.add_incident_resolution(
            incident_id="incident_042",
            title="Checkout payment processing timeouts",
            root_cause="New payment gateway had different timeout thresholds",
            resolution="Adjusted timeout configurations and added monitoring alerts."
        )
        
        # Add migration guides
        kb.add_migration_guide(
            stage=1,
            doc_title="Stage-1-Onboarding.md",
            content="""
Stage 1: Platform Onboarding

1. Create merchant account
2. Configure basic storefront settings
3. Set up product catalog
4. Configure payment methods

Common Issues:
- Ensure payment gateway credentials are valid
- Product feed must include all required fields
"""
        )
        
        kb.add_migration_guide(
            stage=2,
            doc_title="Stage-2-Webhook-Setup.md",
            content="""
Stage 2: Webhook Configuration

Webhooks enable real-time order and inventory notifications.

Required Steps:
1. Go to Settings > Webhooks
2. Register webhook endpoint URL (must be HTTPS)
3. Test webhook delivery with test button
4. Monitor webhook logs for errors

Common Issues:
- Webhook endpoint timeout or not responding (check SSL certificate)
- Webhook endpoint returning 4xx or 5xx errors
- Firewall blocking webhook delivery

If webhooks aren't working:
1. Verify endpoint URL is accessible
2. Check firewall rules
3. Enable webhook retry in settings
4. Review webhook logs for details
"""
        )
        
        kb.add_migration_guide(
            stage=2,
            doc_title="Stage-2-API-Integration.md",
            content="""
Stage 2: API Integration

The new API uses OAuth 2.0 for authentication.

Setup:
1. Create API credentials in dashboard
2. Store client_id and client_secret securely
3. Request access token before API calls
4. Include token in Authorization header

Common Issues:
- 401 Unauthorized: Token expired or invalid
- 403 Forbidden: Token lacks required scopes
- Rate limiting: Default 1000 requests/hour

Best Practices:
- Rotate credentials every 90 days
- Use different credentials for dev/prod
- Implement exponential backoff for retries
"""
        )
        
        kb.add_migration_guide(
            stage=3,
            doc_title="Stage-3-Advanced-Features.md",
            content="""
Stage 3: Advanced Features

Enable advanced analytics and automation features.

Features:
- Custom webhooks
- Batch API operations
- Advanced analytics
- Workflow automation

Setup Instructions:
1. Review feature documentation
2. Create necessary API credentials
3. Test in sandbox environment
4. Deploy to production

Common Issues:
- Sandbox and production use different credentials
- API rate limits apply to all requests
- Some features require additional permissions
"""
        )
        
        kb.add_migration_guide(
            stage=4,
            doc_title="Stage-4-Optimization.md",
            content="""
Stage 4: Performance Optimization

Optimize platform performance for production scale.

Topics:
- Caching strategies
- Database query optimization
- API response time optimization
- Monitoring and alerting

Recommended Actions:
1. Set up performance monitoring
2. Configure CDN for static assets
3. Enable API response caching
4. Set up alerts for degraded performance

Troubleshooting:
- Slow API responses: Check database indexes
- High webhook latency: Check endpoint performance
- Rate limiting issues: Batch requests or request quota increase
"""
        )
        
        logger.info("[KnowledgeBase] Seeded with example data")
