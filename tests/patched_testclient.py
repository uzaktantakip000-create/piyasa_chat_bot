import contextlib
import math
import typing
import warnings
from urllib.parse import urljoin

import anyio
import httpx
from starlette.testclient import (
    ASGI2App,
    ASGI3App,
    _AsyncBackend,
    _RequestData,
    _TestClientTransport,
    _Upgrade,
    _WrapASGI2,
    StapledObjectStream,
    _is_asgi3,
)
from starlette.types import ASGIApp


class PatchedTestClient(httpx.Client):
    """Drop-in replacement for Starlette's TestClient without the deprecated httpx app shortcut."""

    __test__ = False
    task: "typing.Future[None]"
    portal: typing.Optional[anyio.abc.BlockingPortal] = None

    def __init__(
        self,
        app: ASGIApp,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: str = "asyncio",
        backend_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
        cookies: httpx._client.CookieTypes = None,
        headers: typing.Optional[typing.Dict[str, str]] = None,
    ) -> None:
        self.async_backend = _AsyncBackend(
            backend=backend, backend_options=backend_options or {}
        )
        if _is_asgi3(app):
            app = typing.cast(ASGI3App, app)
            asgi_app = app
        else:
            app = typing.cast(ASGI2App, app)  # type: ignore[assignment]
            asgi_app = _WrapASGI2(app)  # type: ignore[arg-type]
        self.app = asgi_app
        self.app_state: typing.Dict[str, typing.Any] = {}
        transport = _TestClientTransport(
            self.app,
            portal_factory=self._portal_factory,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
            app_state=self.app_state,
        )
        if headers is None:
            headers = {}
        headers.setdefault("user-agent", "testclient")
        super().__init__(
            base_url=base_url,
            headers=headers,
            transport=transport,
            follow_redirects=True,
            cookies=cookies,
        )

    @contextlib.contextmanager
    def _portal_factory(self) -> typing.Generator[anyio.abc.BlockingPortal, None, None]:
        if self.portal is not None:
            yield self.portal
        else:
            with anyio.from_thread.start_blocking_portal(
                **self.async_backend
            ) as portal:
                yield portal

    def _choose_redirect_arg(
        self,
        follow_redirects: typing.Optional[bool],
        allow_redirects: typing.Optional[bool],
    ) -> typing.Union[bool, httpx._client.UseClientDefault]:
        redirect: typing.Union[
            bool, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT
        if allow_redirects is not None:
            message = (
                "The `allow_redirects` argument is deprecated. "
                "Use `follow_redirects` instead."
            )
            warnings.warn(message, DeprecationWarning)
            redirect = allow_redirects
        if follow_redirects is not None:
            redirect = follow_redirects
        elif allow_redirects is not None and follow_redirects is not None:
            raise RuntimeError(  # pragma: no cover
                "Cannot use both `allow_redirects` and `follow_redirects`."
            )
        return redirect

    def request(  # type: ignore[override]
        self,
        method: str,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[_RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Any = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        url = self.base_url.join(url)
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().request(
            method,
            url,
            content=content,
            data=data,  # type: ignore[arg-type]
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def get(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().get(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def options(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[_RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Any = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().options(
            url,
            content=content,
            data=data,  # type: ignore[arg-type]
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def head(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().head(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def post(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[_RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Any = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().post(
            url,
            content=content,
            data=data,  # type: ignore[arg-type]
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def put(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[_RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Any = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().put(
            url,
            content=content,
            data=data,  # type: ignore[arg-type]
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def patch(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        content: typing.Optional[httpx._types.RequestContent] = None,
        data: typing.Optional[_RequestData] = None,
        files: typing.Optional[httpx._types.RequestFiles] = None,
        json: typing.Any = None,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().patch(
            url,
            content=content,
            data=data,  # type: ignore[arg-type]
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def delete(  # type: ignore[override]
        self,
        url: httpx._types.URLTypes,
        *,
        params: typing.Optional[httpx._types.QueryParamTypes] = None,
        headers: typing.Optional[httpx._types.HeaderTypes] = None,
        cookies: typing.Optional[httpx._types.CookieTypes] = None,
        auth: typing.Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: typing.Optional[bool] = None,
        allow_redirects: typing.Optional[bool] = None,
        timeout: typing.Union[
            httpx._client.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> httpx.Response:
        redirect = self._choose_redirect_arg(follow_redirects, allow_redirects)
        return super().delete(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def websocket_connect(
        self, url: str, subprotocols: typing.Sequence[str] = None, **kwargs: typing.Any
    ) -> typing.Any:
        url = urljoin("ws://testserver", url)
        headers = kwargs.get("headers", {})
        headers.setdefault("connection", "upgrade")
        headers.setdefault("sec-websocket-key", "testserver==")
        headers.setdefault("sec-websocket-version", "13")
        if subprotocols is not None:
            headers.setdefault("sec-websocket-protocol", ", ".join(subprotocols))
        kwargs["headers"] = headers
        try:
            super().request("GET", url, **kwargs)
        except _Upgrade as exc:
            session = exc.session
        else:
            raise RuntimeError("Expected WebSocket upgrade")  # pragma: no cover

        return session

    def __enter__(self) -> "PatchedTestClient":
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(
                anyio.from_thread.start_blocking_portal(**self.async_backend)
            )

            @stack.callback
            def reset_portal() -> None:
                self.portal = None

            self.stream_send = StapledObjectStream(
                *anyio.create_memory_object_stream(math.inf)
            )
            self.stream_receive = StapledObjectStream(
                *anyio.create_memory_object_stream(math.inf)
            )
            self.task = portal.start_task_soon(self.lifespan)
            portal.call(self.wait_startup)

            @stack.callback
            def wait_shutdown() -> None:
                portal.call(self.wait_shutdown)

            self.exit_stack = stack.pop_all()

        return self

    def __exit__(self, *args: typing.Any) -> None:
        self.exit_stack.close()

    async def lifespan(self) -> None:
        scope = {"type": "lifespan", "state": self.app_state}
        try:
            await self.app(scope, self.stream_receive.receive, self.stream_send.send)
        finally:
            await self.stream_send.send(None)

    async def wait_startup(self) -> None:
        await self.stream_receive.send({"type": "lifespan.startup"})

        async def receive() -> typing.Any:
            message = await self.stream_send.receive()
            if message is None:
                self.task.result()
            return message

        message = await receive()
        assert message["type"] in (
            "lifespan.startup.complete",
            "lifespan.startup.failed",
        )
        if message["type"] == "lifespan.startup.failed":
            await receive()

    async def wait_shutdown(self) -> None:
        async def receive() -> typing.Any:
            message = await self.stream_send.receive()
            if message is None:
                self.task.result()
            return message

        async with self.stream_send:
            await self.stream_receive.send({"type": "lifespan.shutdown"})
            message = await receive()
            assert message["type"] in (
                "lifespan.shutdown.complete",
                "lifespan.shutdown.failed",
            )
            if message["type"] == "lifespan.shutdown.failed":
                await receive()
