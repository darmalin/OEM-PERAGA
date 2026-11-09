import { createFileRoute } from "@tanstack/react-router";

import { ReasonPage } from "./-reason";

export const Route = createFileRoute("/app/exhibitor-orders/$orderId/cancel")({ component: CancelOrder });

function CancelOrder() {
  const { orderId } = Route.useParams();
  return <ReasonPage orderId={orderId} kind="cancel" />;
}
