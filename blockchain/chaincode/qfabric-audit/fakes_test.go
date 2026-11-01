package main

import (
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/v2/pkg/cid"
	"github.com/hyperledger/fabric-chaincode-go/v2/shim"
	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
	"github.com/hyperledger/fabric-protos-go-apiv2/ledger/queryresult"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// fakeStub is a minimal in-memory ledger implementing the stub methods the
// contract uses. Unused interface methods panic via the nil embedded value.
type fakeStub struct {
	shim.ChaincodeStubInterface
	state  map[string][]byte
	txID   string
	txTime time.Time
	events map[string][]byte
}

func newFakeStub() *fakeStub {
	return &fakeStub{
		state:  map[string][]byte{},
		txTime: time.Date(2026, 11, 1, 10, 0, 3, 0, time.UTC),
		events: map[string][]byte{},
	}
}

func (s *fakeStub) GetState(key string) ([]byte, error) { return s.state[key], nil }
func (s *fakeStub) PutState(key string, value []byte) error {
	s.state[key] = append([]byte(nil), value...)
	return nil
}
func (s *fakeStub) CreateCompositeKey(objectType string, attributes []string) (string, error) {
	return shim.CreateCompositeKey(objectType, attributes)
}
func (s *fakeStub) GetTxID() string { return s.txID }
func (s *fakeStub) GetTxTimestamp() (*timestamppb.Timestamp, error) {
	return timestamppb.New(s.txTime), nil
}
func (s *fakeStub) SetEvent(name string, payload []byte) error {
	s.events[name] = payload
	return nil
}
func (s *fakeStub) GetStateByPartialCompositeKey(objectType string, attributes []string) (shim.StateQueryIteratorInterface, error) {
	prefix, err := shim.CreateCompositeKey(objectType, attributes)
	if err != nil {
		return nil, err
	}
	var keys []string
	for k := range s.state {
		if strings.HasPrefix(k, prefix) {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	it := &fakeIterator{}
	for _, k := range keys {
		it.items = append(it.items, &queryresult.KV{Key: k, Value: s.state[k]})
	}
	return it, nil
}

type fakeIterator struct {
	shim.StateQueryIteratorInterface
	items []*queryresult.KV
	pos   int
}

func (it *fakeIterator) HasNext() bool { return it.pos < len(it.items) }
func (it *fakeIterator) Next() (*queryresult.KV, error) {
	kv := it.items[it.pos]
	it.pos++
	return kv, nil
}
func (it *fakeIterator) Close() error { return nil }

// fakeIdentity stands in for the caller's X.509 identity.
type fakeIdentity struct {
	cid.ClientIdentity
	mspID string
}

func (f fakeIdentity) GetMSPID() (string, error) { return f.mspID, nil }
func (f fakeIdentity) GetID() (string, error)    { return "x509::CN=User1@" + f.mspID, nil }

// ledger couples one shared fake stub with per-call caller identities.
type ledger struct {
	stub *fakeStub
	n    int
}

func newLedger() *ledger { return &ledger{stub: newFakeStub()} }

// as returns a transaction context for a caller from mspID, with a fresh
// Fabric transaction ID.
func (l *ledger) as(t *testing.T, mspID string) contractapi.TransactionContextInterface {
	t.Helper()
	l.n++
	l.stub.txID = "fabric-tx-" + string(rune('a'+l.n))
	ctx := &contractapi.TransactionContext{}
	ctx.SetStub(l.stub)
	ctx.SetClientIdentity(fakeIdentity{mspID: mspID})
	return ctx
}
