FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /proxy .
FROM gcr.io/distroless/static
COPY --from=build /proxy /proxy
EXPOSE 8443
ENTRYPOINT ["/proxy"]
