import React, { useState, useEffect, useCallback, useContext } from 'react';
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
  receipt_pdf_url?: string; // Nytt fält för kvitto
  // Potentially more fields from the offer and creator models might be needed
  // For example, if the API returns nested creator info:
  // creator?: { display_name?: string; username: string; platform_name?: string };
  last_payout_method?: string;
  last_payout_reference?: string;
  valuation_confidence?: number;
  price_low_eur?: number;
  price_high_eur?: number;
  title?: string;
  description?: string;
}

// Interface for raw deal data coming from the API
interface RawApiDeal {
  id: string;
  creator?: { email?: string; [key: string]: unknown }; // Changed to unknown
  email?: string; // Kan finnas på toppnivå också
  price_median_eur?: number; // Antas vara i cent från API
  amount_cents?: number;     // Antas vara i cent från API (för OFFER_CREATED)
  status?: string;
  created_at?: string; // ISO string
  pdf_url?: string;
  receipt_pdf_url?: string;
  last_payout_method?: string;
  last_payout_reference?: string;
  valuation_confidence?: number;
  price_low_eur?: number;    // Antas vara i cent
  price_high_eur?: number;   // Antas vara i cent
  title?: string;
  description?: string;
  // För att tillåta andra oväntade fält från API:et utan att TypeScript klagar
  [key: string]: unknown; // Changed to unknown
}

// Updated SseEventData to be more specific if all payload types are known
interface SseEventData {
  type: "OFFER_CREATED" | "OFFER_VALUATED" | "OFFER_PAYOUT_REQUESTED" | "OFFER_PAYOUT_COMPLETED" | "OFFER_RECEIPT_GENERATED" | string; // string for potential unknown/future types
  payload: OfferCreatedPayload | OfferValuatedPayload | OfferPayoutRequestedPayload | OfferPayoutCompletedPayload | OfferReceiptGeneratedPayload | { offer_id?: string; id?: string; [key: string]: unknown }; // Changed any to unknown
}

// Specifika payload-typer baserade på Avro-scheman (förenklat här)
interface OfferCreatedPayload {
    id: string; // This IS the offer_id for OFFER_CREATED events
    creator_id: string;
    title: string;
    description?: string;
    amount_cents: number;
    currency_code: string;
    status: string;
    created_at_timestamp: number; // micros
    creator_email?: string; // Detta fält finns inte i offer_created.avsc, behöver hämtas på annat sätt om det ska visas direkt
}
interface OfferValuatedPayload {
    offer_id: string;
    price_low_eur: number;    // Dessa är i cent i Avro
    price_median_eur: number; // Dessa är i cent i Avro
    price_high_eur: number;   // Dessa är i cent i Avro
    valuation_confidence?: number;
    status: string;
}
interface OfferPayoutRequestedPayload {
    offer_id: string;
    status?: string; // t.ex. "PAYOUT_REQUESTED"
}
interface OfferPayoutCompletedPayload {
    offer_id: string;
    payout_method: string;
    reference_id: string;
    status: "SUCCESS" | "FAILURE";
    failure_reason?: string;
    amount_cents: number;
    currency_code: string;
}
interface OfferReceiptGeneratedPayload {
    offer_id: string;
    receipt_url: string;
    receipt_hash_sha256?: string;
}

// Dummy context for date-fns if not provided globally or via a proper provider
const DateFnsContext = React.createContext({ format, parseISO });

const DealDetailsDrawer: React.FC<{
  deal: Deal | null;
  isOpen: boolean;
  onClose: () => void;
  onRetryPayout: (offerId: string) => Promise<void>;
}> = ({ deal, isOpen, onClose, onRetryPayout }) => {
  const { format, parseISO } = useContext(DateFnsContext);
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
          <p><strong>Title:</strong> {deal.title || 'N/A'}</p>
          <p><strong>Price (Median):</strong> {deal.price_eur !== undefined ? deal.price_eur.toFixed(2) : 'N/A'} EUR</p>
          {deal.price_low_eur !== undefined && <p><strong>Price Low:</strong> {deal.price_low_eur.toFixed(2)} EUR</p>}
          {deal.price_high_eur !== undefined && <p><strong>Price High:</strong> {deal.price_high_eur.toFixed(2)} EUR</p>}
          <p><strong>Status:</strong> <Badge>{deal.status}</Badge></p>
          <p><strong>Created:</strong> {deal.created_at ? format(parseISO(deal.created_at), 'PPpp') : 'N/A'}</p>
          {deal.valuation_confidence !== undefined && <p><strong>Valuation Confidence:</strong> {deal.valuation_confidence.toFixed(2)}</p>}
          {deal.pdf_url && (
            <p><strong>Termsheet:</strong> <a href={deal.pdf_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">View Termsheet PDF</a></p>
          )}
          {deal.receipt_pdf_url && (
            <p><strong>Receipt:</strong> <a href={deal.receipt_pdf_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">View Receipt PDF</a></p>
          )}
          {deal.last_payout_method && <p><strong>Last Payout Method:</strong> {deal.last_payout_method}</p>}
          {deal.last_payout_reference && <p><strong>Last Payout Ref:</strong> {deal.last_payout_reference}</p>}
        </div>
        <DrawerFooter className="pt-2">
          <Button onClick={() => onRetryPayout(deal.id)} disabled={!deal || deal.status === 'PAID_OUT' || deal.status === 'PAYOUT_REQUESTED'}>
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

  // API base URL - should come from .env
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'; // Default for local dev

  const fetchDeals = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    try {
      const accessToken = await getAccessTokenSilently();
      const response = await axios.get<{ deals?: RawApiDeal[]; results?: RawApiDeal[] }>(`${API_BASE_URL}/internal/deals?limit=50`, { 
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const rawDeals = response.data.deals || response.data.results || (Array.isArray(response.data) ? response.data : []);
      
      const fetchedDeals = rawDeals.map((d: RawApiDeal): Deal => ({
        id: d.id, 
        email: (d.creator?.email as string) || (d.email as string) || 'N/A',
        // Konvertera från cent till Euro, hantera om price_median_eur eller amount_cents används
        price_eur: d.price_median_eur !== undefined ? d.price_median_eur / 100 : (d.amount_cents !== undefined ? d.amount_cents / 100 : 0),
        status: (d.status as string) || "UNKNOWN",
        created_at: (d.created_at as string) || new Date().toISOString(),
        pdf_url: d.pdf_url as string | undefined,
        receipt_pdf_url: d.receipt_pdf_url as string | undefined,
        last_payout_method: d.last_payout_method as string | undefined,
        last_payout_reference: d.last_payout_reference as string | undefined,
        valuation_confidence: d.valuation_confidence as number | undefined,
        price_low_eur: d.price_low_eur !== undefined ? d.price_low_eur / 100 : undefined,
        price_high_eur: d.price_high_eur !== undefined ? d.price_high_eur / 100 : undefined,
        title: d.title as string | undefined,
        description: d.description as string | undefined,
      })); 
      setDeals(fetchedDeals);
    } catch (error) {
      console.error("Error fetching deals:", error);
      toast.error("Failed to fetch deals.");
      setDeals([]);
    }
    setIsLoading(false);
  }, [getAccessTokenSilently, isAuthenticated, API_BASE_URL]);

  useEffect(() => {
    fetchDeals();
  }, [fetchDeals]);

  // SSE Effect Hook
  useEffect(() => {
    if (!isAuthenticated) return;
    const eventSourceUrl = `${API_BASE_URL}/offers/events/deals`;
    console.log(`Connecting to SSE: ${eventSourceUrl}`);
    const eventSource = new EventSource(eventSourceUrl);

    eventSource.onopen = () => console.log("SSE connection opened for deals.");

    eventSource.onmessage = (event) => {
      if (event.data === ":heartbeat") return;
      try {
        const eventData = JSON.parse(event.data) as SseEventData;
        console.log("SSE message received:", eventData);

        setDeals(prevDeals => {
          let offerIdToUpdate: string | undefined;
          const { payload } = eventData;

          if (payload && typeof payload === 'object') {
            // Check for 'id' (primarily for OFFER_CREATED)
            if ('id' in payload && typeof (payload as { id?: string }).id === 'string') {
              offerIdToUpdate = (payload as { id: string }).id;
            }
            // Check for 'offer_id' (for other event types), this can overwrite if 'id' was also found but this is more specific for non-create events.
            if ('offer_id' in payload && typeof (payload as { offer_id?: string }).offer_id === 'string') {
              offerIdToUpdate = (payload as { offer_id: string }).offer_id;
            }
          }

          if (!offerIdToUpdate) {
            console.warn("SSE event payload missing a valid string ID (offer_id or id for OFFER_CREATED)", payload);
            return prevDeals;
          }

          // Logic for OFFER_CREATED
          if (eventData.type === "OFFER_CREATED") {
            if (prevDeals.some(d => d.id === offerIdToUpdate)) return prevDeals; // Avoid duplicates
            const createdPayload = payload as OfferCreatedPayload;
            const newDeal: Deal = {
              id: createdPayload.id,
              email: createdPayload.creator_email || 'N/A',
              price_eur: createdPayload.amount_cents / 100,
              status: createdPayload.status,
              created_at: new Date(createdPayload.created_at_timestamp / 1000).toISOString(),
              title: createdPayload.title,
              description: createdPayload.description,
            };
            return [newDeal, ...prevDeals];
          }
          
          // Logic for updating existing deals
          return prevDeals.map(deal => {
            if (deal.id === offerIdToUpdate) {
              let updatedFields: Partial<Deal> = {};
              switch (eventData.type) {
                case "OFFER_VALUATED": {
                  const valuatedPayload = payload as OfferValuatedPayload;
                  updatedFields = {
                    status: valuatedPayload.status,
                    price_eur: valuatedPayload.price_median_eur / 100,
                    price_low_eur: valuatedPayload.price_low_eur / 100,
                    price_high_eur: valuatedPayload.price_high_eur / 100,
                    valuation_confidence: valuatedPayload.valuation_confidence,
                  };
                  break;
                }
                case "OFFER_PAYOUT_REQUESTED": {
                  const payoutRequestedPayload = payload as OfferPayoutRequestedPayload;
                  updatedFields = { status: payoutRequestedPayload.status || "PAYOUT_REQUESTED" };
                  break;
                }
                case "OFFER_PAYOUT_COMPLETED": {
                  const payoutCompletedPayload = payload as OfferPayoutCompletedPayload;
                  updatedFields = {
                    status: payoutCompletedPayload.status,
                    last_payout_method: payoutCompletedPayload.payout_method,
                    last_payout_reference: payoutCompletedPayload.reference_id,
                  };
                  break;
                }
                case "OFFER_RECEIPT_GENERATED": {
                  const receiptPayload = payload as OfferReceiptGeneratedPayload;
                  updatedFields = { receipt_pdf_url: receiptPayload.receipt_url };
                  break;
                }
              }
              return { ...deal, ...updatedFields };
            }
            return deal;
          });
        });
      } catch (error) {
        console.error("Error parsing SSE message or updating state:", error, "Raw data:", event.data);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE error:", error);
      toast.error("Connection to real-time deal updates lost.");
    };

    return () => {
      console.log("Closing SSE connection for deals.");
      eventSource.close();
    };
  }, [isAuthenticated, API_BASE_URL]); 

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
        `${API_BASE_URL}/internal/payouts/offers/${offerId}/retry_payout`, 
        {},
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        }
      );
      if (response.status === 202) {
        toast.success(`Payout retry initiated successfully for offer ID: ${offerId.substring(0,8)}...`);
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
    <DateFnsContext.Provider value={{ format, parseISO }}>
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
                  <TableCell>{deal.created_at ? format(parseISO(deal.created_at), 'yyyy-MM-dd HH:mm') : 'N/A'}</TableCell>
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
    </DateFnsContext.Provider>
  );
};

export default DealsPage; 