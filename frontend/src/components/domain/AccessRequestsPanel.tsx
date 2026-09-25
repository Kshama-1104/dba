import React, { useEffect, useState } from "react";
import { accessRequestsApi, AccessRequest } from "../../api/access_requests";
import { Card, CardHeader, CardContent } from "../ui/Card";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { ShieldCheck, Check, X, AlertCircle } from "lucide-react";

export const AccessRequestsPanel: React.FC = () => {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadRequests = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await accessRequestsApi.list();
      setRequests(data);
    } catch (err: any) {
      setError(err.message || "Failed to load access requests");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRequests();
  }, []);

  const handleDecision = async (id: number, decision: "accepted" | "rejected") => {
    try {
      const res = await accessRequestsApi.decide(id, decision);
      if (res.temporary_password) {
        setSuccessMessage(`Approved! Temporary password for user: ${res.temporary_password}`);
      } else {
        setSuccessMessage(res.message);
      }
      loadRequests();
    } catch (err: any) {
      setError(err.message || "Failed to process decision");
    }
  };

  if (isLoading) return <div className="p-4 text-sm">Loading requests...</div>;

  return (
    <Card>
      <CardHeader 
        title="Pending Access Requests" 
        description="Users requesting Reviewer or Editor access to this workspace."
      />
      <CardContent>
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 text-xs rounded flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> {error}
          </div>
        )}
        {successMessage && (
          <div className="mb-4 p-3 bg-green-50 text-green-700 text-xs rounded border border-green-200">
            {successMessage}
          </div>
        )}
        
        {requests.length === 0 ? (
          <EmptyState
            icon={<ShieldCheck className="w-6 h-6" />}
            title="No Pending Requests"
            description="There are no users currently waiting for approval."
          />
        ) : (
          <div className="space-y-3">
            {requests.map(req => (
              <div key={req.id} className="flex items-center justify-between p-3 border border-border rounded-lg bg-background">
                <div>
                  <p className="text-sm font-semibold text-near-black">
                    User #{req.requester_id}
                  </p>
                  <p className="text-xs text-muted">
                    Requested Role: <span className="font-medium uppercase">{req.request_type.replace('_access', '')}</span>
                  </p>
                  <p className="text-[10px] text-muted mt-1">
                    Requested on: {new Date(req.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => handleDecision(req.id, "rejected")}
                    leftIcon={<X className="w-3.5 h-3.5" />}
                  >
                    Reject
                  </Button>
                  <Button 
                    size="sm" 
                    variant="primary"
                    onClick={() => handleDecision(req.id, "accepted")}
                    leftIcon={<Check className="w-3.5 h-3.5" />}
                  >
                    Approve
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
