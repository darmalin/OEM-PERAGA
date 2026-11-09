import { createFileRoute } from "@tanstack/react-router";

import { ReasonPage } from "./-reason";

export const Route = createFileRoute("/app/exhibitor-orders/$orderId/return")({ component: ReturnOrder });

function ReturnOrder() {
  const { orderId } = Route.useParams();
  return <ReasonPage orderId={orderId} kind="return" />;
}
