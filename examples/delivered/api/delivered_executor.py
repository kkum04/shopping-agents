# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The delivered example's tool executor: sign-in errors reach the model as guidance
for the customer instead of the framework's "temporarily unavailable" line. Passed as
``executor_class`` to the agent, which the host's button routes reuse."""

from __future__ import annotations

from commerce_common.streaming import ToolOutcome
from shopping_agent.executor import ShoppingToolExecutor

from .delivered_auth import SignInRequired, TokenExpired
from .delivered_cart import CartRejected


class DeliveredToolExecutor(ShoppingToolExecutor):
    sign_in_required_text = (
        "로그인이 필요합니다: {feature}은(는) delivered 계정으로 로그인한 뒤 쓸 수 있습니다. "
        "손님에게 로그인을 안내하고, 같은 호출을 다시 시도하지 마세요."
    )
    token_expired_text = (
        "로그인이 만료되어 다시 로그인이 필요합니다. 손님에게 다시 로그인하라고 안내하고, "
        "같은 호출을 다시 시도하지 마세요."
    )

    def domain_error(self, error: Exception) -> ToolOutcome | None:
        if isinstance(error, SignInRequired):
            feature = self._sanitize(str(error), 80) or "이 기능"
            return ToolOutcome.error(self.sign_in_required_text.format(feature=feature))
        if isinstance(error, TokenExpired):
            return ToolOutcome.error(self.token_expired_text)
        if isinstance(error, CartRejected):
            return ToolOutcome.error(
                self._sanitize(str(error), 300) or "장바구니 요청이 거절되었습니다."
            )
        return super().domain_error(error)
