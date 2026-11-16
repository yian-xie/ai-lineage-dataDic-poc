from lineage_poc.parsers.dotnet_data import parse_ef_snapshots


def test_ef_snapshot_preserves_literals_nested_columns_and_binding_scope(tmp_path):
    path = tmp_path / "src/App/Infrastructure/Migrations/AppDbContextModelSnapshot.cs"
    path.parent.mkdir(parents=True)
    path.write_text('''class Snapshot { void Build() {
        modelBuilder.Entity("App.Account", b => {
            b.Property<string>("AccountId").HasColumnType("text").HasColumnName("account_id");
            b.ComplexProperty<object>("Facility", "App.Facility", b1 => {
                b1.Property<string>("Id").HasColumnType("text").HasColumnName("facility_id");
            });
            b.Property<string>("Unknown");
            b.ToTable("account", "profile");
        });
    }}''', encoding="utf-8")
    entity = tmp_path / "src/Account.cs"
    entity.write_text('''namespace App;
    class Account {
        /// <summary>Declared account identifier.</summary>
        public string AccountId { get; set; }
    }''', encoding="utf-8")
    result = parse_ef_snapshots(tmp_path)
    assert {(row["source_column"], row["target_column"]) for row in result["mappings"]} == {("AccountId", "account_id"), ("Facility.Id", "facility_id")}
    assert all(row["mapping_kind"] == "ef_property_binding" for row in result["mappings"])
    assert result["nodes"][1]["type"] == "POSTGRES_RELATION"
    assert result["nodes"][1]["properties"]["name"] == "profile.account"
    assert result["unresolved"][0]["reason"] == "ef_column_name_not_explicit"
    assert not result["coverage"]["runtime_verified"]
    assert result["mappings"][0]["property_metadata"]["description"] == "Declared account identifier."


def test_separate_owned_property_block_reuses_declared_table_without_duplicate_edge(tmp_path):
    path = tmp_path / "src/AppDbContextModelSnapshot.cs"
    path.parent.mkdir(parents=True)
    path.write_text('''class Snapshot { void Build() {
        modelBuilder.Entity("App.Account", b => {
            b.Property<string>("Id").HasColumnName("id");
            b.ToTable("account", "profile");
        });
        modelBuilder.Entity("App.Account", b => {
            b.OwnsOne("App.Reference", "Reference", b1 => {
                b1.Property<string>("Code").HasColumnName("reference_code");
                b1.ToTable("account", "profile");
            });
            b.OwnsOne("App.Json", "Payload", b1 => {
                b1.ToJson();
                b1.Property<string>("Code").HasColumnName("not_a_column");
            });
            b.OwnsOne("App.Json", "Document", b1 => {
                b1.ToJson("document").HasColumnType("jsonb");
                b1.Property<string>("Code");
            });
        });
    }}''', encoding="utf-8")
    result = parse_ef_snapshots(tmp_path)
    assert len(result["edges"]) == 1
    assert {(row["source_column"], row["target_column"]) for row in result["mappings"]} == {("Id", "id"), ("Reference.Code", "reference_code"), ("Document", "document")}
    assert result["mappings"][-1]["mapping_kind"] == "ef_json_document_binding"
    assert result["mappings"][-1]["data_type"] == "jsonb"
    assert result["unresolved"][0]["reason"] == "ef_owned_json_or_separate_table_not_supported"


def test_migration_up_and_mapper_assignments_are_evidence_not_runtime_lineage(tmp_path):
    migration = tmp_path / "src/App/Infrastructure/Migrations/AddColumn.cs"
    migration.parent.mkdir(parents=True)
    migration.write_text('''class Migration {
        void Up() { migrationBuilder.AddColumn<string>(name: "account_id", table: "account", type: "text"); }
        void Down() { migrationBuilder.DropColumn(name: "account_id", table: "account"); }
    }''', encoding="utf-8")
    mapper = tmp_path / "src/AccountMapper.cs"
    mapper.write_text("class Mapper { void Map() { target.AccountId = source.AccountId; } }", encoding="utf-8")
    result = parse_ef_snapshots(tmp_path)
    assert [item["operation"] for item in result["migration_evidence"][0]["operations"]] == ["AddColumn"]
    assert not result["migration_evidence"][0]["executed"]
    assert result["assignment_evidence"][0]["assignments"][0]["expression"] == "target.AccountId = source.AccountId"
    assert result["mappings"] == []


def test_event_builder_maps_collection_lambda_and_foreach_properties(tmp_path):
    snapshot = tmp_path / "src/AppDbContextModelSnapshot.cs"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('''namespace App;
    class Snapshot { void Build() {
        modelBuilder.Entity("App.AccountProfile", b => {
            b.Property<string>("Id").HasColumnName("id");
            b.ToTable("account_profile", "profile");
        });
        modelBuilder.Entity("App.AccountProfileIdentifier", b => {
            b.Property<string>("Code").HasColumnName("code");
            b.ToTable("account_profile_identifier", "profile");
        });
        modelBuilder.Entity("App.AccountBalance", b => {
            b.Property<string>("AccountId").HasColumnName("account_id");
            b.Property<decimal>("Amount").HasColumnName("amount");
            b.ToTable("account_balance", "transaction");
        });
    }}''', encoding="utf-8")
    source = tmp_path / "src/Builder.cs"
    entity = tmp_path / "src/AccountProfile.cs"
    entity.write_text('''using System.Collections.Generic;
    namespace App;
    public class AccountProfile { public ICollection<AccountProfileIdentifier> Identifiers { get; set; } }
    public class AccountProfileIdentifier { public string Code { get; set; } }
    public class AccountBalance { public string AccountId { get; set; } public decimal Amount { get; set; } }
    ''', encoding="utf-8")
    source.write_text('''using System.Collections.Generic;
    using System.Linq;
    using App;
    using Api.Shared.Clients.Events.Sample;
    namespace App.Processor;
    class Builder {
        void BuildProfile(AccountProfile accountProfile) {
            var ids = accountProfile.Identifiers.Select(identifier => new Api.Shared.Clients.Events.Sample.AccountIdentification {
                Value = identifier.Code
            }).ToList();
        }
        void BuildBalance(IReadOnlyCollection<AccountBalance> accountBalances) {
            foreach (var balance in accountBalances) {
                result.AccountBalances.Add(new Api.Shared.Clients.Events.Sample.Balance { AccountId = balance.AccountId, Value = balance.Amount });
            }
        }
    }''', encoding="utf-8")
    result = parse_ef_snapshots(tmp_path)
    mappings = result["event_mappings"]
    assert {(row["source_column"], row["target_column"]) for row in mappings} == {
        ("Code", "Value"), ("AccountId", "AccountId"), ("Amount", "Value")}


def test_all_extracted_fields_receive_typed_event_relationship_or_explicit_gap(tmp_path):
    snapshot = tmp_path / "src/AppDbContextModelSnapshot.cs"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('''class Snapshot { void Build() { modelBuilder.Entity("App.Account", b => {
        b.Property<string>("AccountId").HasColumnName("account_id");
        b.Property<string>("Name").HasColumnName("name");
        b.Property<string>("Unmapped").HasColumnName("unmapped");
        b.ToTable("account", "profile");
    }); }}''', encoding="utf-8")
    builder = tmp_path / "src/EventBuilder.cs"
    builder.write_text('''using App;
    using Event = Api.Shared.Clients.Events.Account;
    class Builder { Event.Profile Build(Account account) {
        return new Event.Profile { AccountId = account.AccountId, AccountName = Upper(account.Name),
            FallbackName = account.Name ?? throw new Exception(account.AccountId) };
    }}''', encoding="utf-8")
    result = parse_ef_snapshots(tmp_path)
    assert {(row["source_column"], row["target_column"]) for row in result["event_mappings"]} == {("AccountId", "AccountId"), ("Name", "AccountName"), ("Name", "FallbackName")}
    assert len(result["field_relationship_assessments"]) == 3
    assert [item["property"] for item in result["field_relationship_assessments"] if item["status"] == "unresolved"] == ["Unmapped"]
    assert result["event_mappings"][1]["transformation_expression"] == "AccountName = Upper(account.Name)"
    assert all(row["mapping_kind"] == "csharp_event_assignment" for row in result["event_mappings"])
    sender = tmp_path / "src/Publisher.cs"
    sender.write_text('''using Event = Api.Shared.Clients.Events.Account;
    class Sender(IOutboxEventPublisher<Event.Profile> publisher) {
        void Send(Event.Profile value) { publisher.PublishAsync(value); }
    }''', encoding="utf-8")
    expanded = parse_ef_snapshots(tmp_path)
    assert any(edge["type"] == "PUBLISHED_VIA" for edge in expanded["edges"])
    assert any(node["type"] == "EVENT_PUBLISHER" and node["properties"]["is_boundary_node"] is True for node in expanded["nodes"])


def test_focused_event_mapping_keeps_wrapping_and_stops_at_publication_boundary():
    from lineage_poc.viewers.graph.tmv import _focused_graph
    graph = {"nodes": [{"id": name, "type": "DOTNET_EVENT", "properties": {"is_boundary_node": name == "publisher"}}
                       for name in ("entity", "event", "other", "envelope", "publisher", "beyond")],
             "edges": [
                 {"source": "entity", "target": "event", "type": "ASSIGNS_TO_EVENT", "properties": {"related_field_mappings": ["selected"]}},
                 {"source": "entity", "target": "other", "type": "ASSIGNS_TO_EVENT", "properties": {"related_field_mappings": ["unrelated"]}},
                 {"source": "event", "target": "envelope", "type": "WRAPPED_IN_EVENT", "properties": {}},
                 {"source": "envelope", "target": "publisher", "type": "PUBLISHED_VIA", "properties": {}},
                 {"source": "publisher", "target": "beyond", "type": "DEPENDS_ON", "properties": {}},
             ]}
    result = _focused_graph(graph, [{"field_id": "selected", "source_relation_id": "entity", "target_relation_id": "event", "target_model_id": "event"}])
    assert {node["id"] for node in result["nodes"]} == {"entity", "event", "envelope", "publisher"}