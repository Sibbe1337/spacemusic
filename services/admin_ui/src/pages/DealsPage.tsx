import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import { useAuth0 } from '@auth0/auth0-react';

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { toast } from "sonner";

// Define an interface for the Deal object based on expected data
interface Deal {
  id: string; 
  email: string; // Assuming creator's email or a contact email for the deal
  price_eur: number; // Placeholder, actual field might be offer.price_median_eur or similar
  status: string;
  created_at: string; // ISO date string
  pdf_url?: string; 
  // Potentially more fields from the offer and creator models might be needed
  // For example, if the API returns nested creator info:
  // creator?: { display_name?: string; username: string; platform_name?: string };
}

const DealDetailsDrawer: React.FC<{
  deal: Deal | null;
  isOpen: boolean;
  onClose: () => void;
  onRetryPayout: (offerId: string) => Promise<void>;
}> = ({ deal, isOpen, onClose, onRetryPayout }) => {
  if (!deal) return null;

  return (
    <Drawer open={isOpen} onOpenChange={(open: boolean) => !open && onClose()}>
      <DrawerContent className="p-4 max-w-md mx-auto">
        <DrawerHeader>
          <DrawerTitle>Deal Details: {deal.id.substring(0, 8)}...</DrawerTitle>
          <DrawerDescription>
            Email: {deal.email}
          </DrawerDescription>
        </DrawerHeader>
        <div className="grid gap-2 px-4 py-2 text-sm">
          <p><strong>Full ID:</strong> {deal.id}</p>
          <p><strong>Price:</strong> {deal.price_eur !== undefined ? deal.price_eur.toFixed(2) : 'N/A'} EUR</p>
          <p><strong>Status:</strong> <Badge>{deal.status}</Badge></p>
          <p><strong>Created:</strong> {format(parseISO(deal.created_at), 'PPpp')}</p>
          {deal.pdf_url && (
            <p><strong>Termsheet:</strong> <a href={deal.pdf_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">View PDF</a></p>
          )}
          <p><strong>Payout Timeline:</strong> (Placeholder for payout timeline)</p>
        </div>
        <DrawerFooter className="pt-2">
          <Button onClick={() => onRetryPayout(deal.id)} disabled={!deal || deal.status === 'PAID_OUT'}>
            Retry Payout
          </Button>
          <DrawerClose asChild>
            <Button variant="outline">Close</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
};

const DealsPage = () => {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  const fetchDeals = useCallback(async () => {
    if (!isAuthenticated) return; // Don't fetch if not authenticated
    setIsLoading(true);
    try {
      const accessToken = await getAccessTokenSilently();
      // The API endpoint /internal/deals needs to be implemented in your backend.
      // It should return a list of deals (offers with relevant details).
      const response = await axios.get('/internal/deals?limit=50', { 
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      // Assuming the API returns { deals: Deal[] } or just Deal[]
      setDeals(response.data.deals || response.data || []); 
    } catch (error) {
      console.error("Error fetching deals:", error);
      toast.error("Failed to fetch deals. Ensure the backend API is running and accessible.");
      setDeals([]);
    }
    setIsLoading(false);
  }, [getAccessTokenSilently, isAuthenticated]);

  useEffect(() => {
    fetchDeals();
  }, [fetchDeals]);

  const handleRowClick = (deal: Deal) => {
    setSelectedDeal(deal);
    setIsDrawerOpen(true);
  };

  const handleRetryPayout = async (offerId: string) => {
    if (!offerId) return;
    toast.info(`Initiating payout retry for offer ID: ${offerId.substring(0,8)}...`);
    try {
      const accessToken = await getAccessTokenSilently();
      const response = await axios.post(
        // This endpoint is defined in services/payouts/routes.py
        // Ensure your gateway/proxy setup allows admin_ui to reach this.
        `/internal/payouts/offers/${offerId}/retry_payout`, 
        {},
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        }
      );
      if (response.status === 202) {
        toast.success(`Payout retry initiated successfully for offer ID: ${offerId.substring(0,8)}...`);
        // Optionally re-fetch deals or update the specific deal's status locally
        fetchDeals(); 
      } else {
        toast.error(`Failed to initiate payout retry. Status: ${response.status}, Message: ${response.data?.detail || response.data?.message || 'Unknown error'}`);
      }
    } catch (error: unknown) {
      console.error("Error retrying payout:", error);
      let errorMessage = "An unknown error occurred while retrying the payout.";
      if (axios.isAxiosError(error) && error.response) {
        errorMessage = error.response.data?.detail || error.response.data?.message || error.message;
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }
      toast.error(errorMessage);
    }
  };

  if (isLoading && deals.length === 0) { // Show loading only if no deals are yet shown
    return <div className="p-4 text-center">Loading deals...</div>;
  }

  return (
    <div className="container mx-auto py-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Deals Management</h1>
        <Button onClick={fetchDeals} variant="outline" disabled={isLoading}>
          {isLoading ? 'Refreshing...' : 'Refresh Deals'}
        </Button>
      </div>
      {deals.length === 0 && !isLoading && <p className="text-center text-muted-foreground">No deals found.</p>}
      {deals.length > 0 && (
        <Table>
          <TableCaption>A list of recent deals. Click a row for details.</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Price (€)</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created At</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {deals.map((deal) => (
              <TableRow key={deal.id} onClick={() => handleRowClick(deal)} className="cursor-pointer hover:bg-muted/50">
                <TableCell className="font-mono text-xs">{deal.id.substring(0,8)}...</TableCell>
                <TableCell>{deal.email}</TableCell>
                <TableCell>{deal.price_eur !== undefined ? deal.price_eur.toFixed(2) : 'N/A'}</TableCell>
                <TableCell><Badge variant={deal.status === 'PAID_OUT' ? 'default' : (deal.status === 'OFFER_READY' ? 'secondary' : 'outline') }>{deal.status}</Badge></TableCell>
                <TableCell>{format(parseISO(deal.created_at), 'yyyy-MM-dd HH:mm')}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <DealDetailsDrawer 
        deal={selectedDeal} 
        isOpen={isDrawerOpen} 
        onClose={() => setIsDrawerOpen(false)} 
        onRetryPayout={handleRetryPayout}
      />
    </div>
  );
};

export default DealsPage; 